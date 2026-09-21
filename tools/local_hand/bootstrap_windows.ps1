[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ProfileSource,
    [string]$NodeId="",
    [Parameter(Mandatory=$true)][string]$RepositoryName,
    [string]$RepositoryPath="",
    [switch]$SingleWriter,
    [string]$SeedRepositoryFrom="",
    [string]$ImplementationCommit="",
    [string]$MailboxUrl="",
    [string]$MailboxBranch="",
    [string]$MailboxSshKey="",
    [string]$KnownHostsFile="",
    [Parameter(Mandatory=$true)][string]$StateRoot,
    [string]$ProjectsRoot="",
    [string]$ServiceAccount="NT AUTHORITY\LOCAL SERVICE",
    [string]$TaskName="LocalHand-v0.1"
)
$ErrorActionPreference="Stop"
if($PSVersionTable.PSEdition -ne 'Core' -or $PSVersionTable.PSVersion.Major -lt 7){throw "Local Hand v0.1 Windows bootstrap requires PowerShell 7 or newer"}
$StageRoot=$null; $MailboxRoot=$null; $RunnerPath=$null; $DeploymentRoot=$null; $CredentialsRoot=$null; $RecoveryInstanceRoot=$null; $RecoveryXmlPath=$null
$DeploymentCreated=$false; $SwitchStarted=$false; $SwitchCommitted=$false; $Succeeded=$false; $UnsafeLiveProcess=$false; $RollbackFailed=$false

function Resolve-Executable([string]$Name){ return (Get-Command $Name -ErrorAction Stop).Source }
function Assert-SafeId([string]$Value,[string]$Field){ if($Value -notmatch '^[A-Za-z0-9._-]{1,128}$'){throw "invalid $Field"} }
$AclHelpers=Join-Path $PSScriptRoot "windows_acl.ps1"
if(-not(Test-Path -LiteralPath $AclHelpers -PathType Leaf)){throw "missing Windows ACL helpers: $AclHelpers"}
function Set-RootAcl([string]$Path){Set-LocalHandExactDirectoryAcl $Path ([System.Security.AccessControl.FileSystemRights]::ReadAndExecute) $false}
function Set-ReadOnlyAcl([string]$Path){Set-LocalHandExactDirectoryAcl $Path ([System.Security.AccessControl.FileSystemRights]::ReadAndExecute) $true}
function Set-ReadOnlyFileAcl([string]$Path){Set-LocalHandExactFileAcl $Path ([System.Security.AccessControl.FileSystemRights]::Read)}
function Set-RuntimePrivateKeyAcl([string]$Path){Set-LocalHandRuntimePrivateKeyAcl $Path}
function Set-WritableAcl([string]$Path){Set-LocalHandExactDirectoryAcl $Path ([System.Security.AccessControl.FileSystemRights]::Modify) $true}
function Get-OwnedScheduledTask {
    $task=Get-ScheduledTask -TaskPath '\' -TaskName $TaskName -ErrorAction SilentlyContinue
    if($null -eq $task){return $null}
    if(@($task).Count -ne 1){throw "existing Scheduled Task ownership is not proven; refusing stop/replace before mutation"}
    $ownedDescription=$task.Description -is [string] -and ($task.Description -eq $TaskOwnerPrefix -or $task.Description.StartsWith("$TaskOwnerPrefix install=",[StringComparison]::Ordinal))
    if(-not $ownedDescription){throw "existing Scheduled Task ownership is not proven; refusing stop/replace before mutation"}
    return $task
}

if($ServiceAccount -ne 'NT AUTHORITY\LOCAL SERVICE'){throw "v0.1 requires ServiceAccount=NT AUTHORITY\LOCAL SERVICE"}
$TaskPrincipalUser='LOCALSERVICE'
$PowerShell=(Get-Process -Id $PID).Path; $Python=Resolve-Executable "python"; $Git=Resolve-Executable "git"; $Ssh=Resolve-Executable "ssh"
$SourceTools=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')); $oldPP=$env:PYTHONPATH
$ProfileSource=[IO.Path]::GetFullPath($ProfileSource)
$profileArgs=@('-m','local_hand.config','--profile',$ProfileSource,'--repository',$RepositoryName)
foreach($pair in @(@('--match-node-id',$NodeId),@('--match-projects-root',$ProjectsRoot),@('--match-repository-path',$RepositoryPath),@('--match-remote-url',$MailboxUrl),@('--match-branch',$MailboxBranch))){if(-not [string]::IsNullOrEmpty($pair[1])){$profileArgs += $pair}}
try{$env:PYTHONPATH=$SourceTools;$profileOutput=& $Python -B @profileArgs;if($LASTEXITCODE -ne 0){throw 'profile admission failed before mutation'};$ProfileSettings=($profileOutput|Out-String)|ConvertFrom-Json}finally{if($null -eq $oldPP){Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue}else{$env:PYTHONPATH=$oldPP}}
if($SingleWriter -and -not $ProfileSettings.single_writer){throw 'SingleWriter assertion differs from profile'}
$NodeId=$ProfileSettings.node_id; $ProjectsRoot=$ProfileSettings.projects_root; $RepositoryPath=$ProfileSettings.repository_path
$MailboxUrl=$ProfileSettings.remote_url; $MailboxBranch=$ProfileSettings.branch; $AdmittedProfileSha=$ProfileSettings.digest
Assert-SafeId $NodeId 'NodeId'; Assert-SafeId $RepositoryName 'RepositoryName'; Assert-SafeId $TaskName 'TaskName'
& $Git check-ref-format "refs/heads/$MailboxBranch" | Out-Null; if($LASTEXITCODE -ne 0){throw "invalid MailboxBranch"}
if($MailboxUrl.Contains("`n") -or $MailboxUrl.Contains("`r")){throw "invalid MailboxUrl"}
# allowed_remote_urls and branch are admitted by the shared profile validator.

Get-ChildItem Env: | Where-Object { $_.Name -like 'GIT_*' -or $_.Name -like 'SSH_*' } | ForEach-Object { Remove-Item -LiteralPath ("Env:"+$_.Name) -ErrorAction SilentlyContinue }
$env:GIT_TERMINAL_PROMPT="0"; $env:GIT_CONFIG_NOSYSTEM="1"; $env:GIT_CONFIG_GLOBAL="NUL"
$DisabledHooks=Join-Path ([IO.Path]::GetTempPath()) ("local-hand-disabled-hooks-bootstrap-"+[guid]::NewGuid().ToString("N")); New-Item -ItemType Directory -Path $DisabledHooks|Out-Null
if(@(Get-ChildItem -LiteralPath $DisabledHooks -Force).Count -ne 0){throw "bootstrap disabled-hooks directory is not empty"}
function Invoke-SafeGit { & $Git --no-pager -c "core.hooksPath=$DisabledHooks" -c core.fsmonitor=false -c submodule.recurse=false -c credential.helper= -c protocol.ext.allow=never @args }
function Assert-NoExecutionFilters([string]$RepoPath){ $o=@(Invoke-SafeGit "-C" $RepoPath "config" "--get-regexp" '^filter\..*\.(clean|smudge|process)$' 2>&1); $rc=$LASTEXITCODE; if($rc -eq 0 -and $o.Count -gt 0){throw "execution-capable Git filter config rejected in $RepoPath"}; if($rc -ne 0 -and $rc -ne 1){throw "cannot inspect Git filter config in $RepoPath"} }

try {
  $repoRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..")); $inside=(Invoke-SafeGit "-C" $repoRoot "rev-parse" "--is-inside-work-tree"|Out-String).Trim(); if($inside -ne "true"){throw "Local Hand bootstrap must run from a Git working tree"}; Assert-NoExecutionFilters $repoRoot
  $ActualSourceHead=(Invoke-SafeGit "-C" $repoRoot "rev-parse" "HEAD"|Out-String).Trim().ToLowerInvariant(); if([string]::IsNullOrWhiteSpace($ImplementationCommit)){$ImplementationCommit=$ActualSourceHead}; if($ImplementationCommit -notmatch '^[0-9a-fA-F]{40,64}$'){throw "implementation commit invalid"}; $ImplementationCommit=$ImplementationCommit.ToLowerInvariant(); if($ImplementationCommit -ne $ActualSourceHead){throw "implementation commit mismatch: claimed=$ImplementationCommit source_head=$ActualSourceHead"}
  $sourceDirty=(Invoke-SafeGit "-C" $repoRoot "status" "--porcelain=v1" "--untracked-files=all" "--" "tools/local_hand"|Out-String).Trim(); if(-not [string]::IsNullOrWhiteSpace($sourceDirty)){throw "tools/local_hand source tree is dirty"}
  . $AclHelpers

  $StateRoot=[IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables($StateRoot)); if([string]::IsNullOrWhiteSpace($ProjectsRoot)){$ProjectsRoot=Join-Path $StateRoot "projects"}; $ProjectsRoot=[IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables($ProjectsRoot)); $rel=[IO.Path]::GetRelativePath($StateRoot,$ProjectsRoot); if($rel.StartsWith("..") -or [IO.Path]::IsPathRooted($rel)){throw "ProjectsRoot must stay under StateRoot for v0.1 blast-radius confinement"}
  if($rel -eq "."){throw "ProjectsRoot must be a strict descendant of StateRoot"}
  $userProfile=[IO.Path]::GetFullPath($env:USERPROFILE); foreach($exe in @($PowerShell,$Python,$Git,$Ssh)){ $full=[IO.Path]::GetFullPath($exe); if($full.StartsWith($userProfile,[StringComparison]::OrdinalIgnoreCase)){throw "Local Hand service account requires system-wide executable, not user-profile path: $full"} }
  # Validation argv, timeout and replay_safe come from the supplied profile.

  $SourceTools=Join-Path $repoRoot "tools"; $oldPP=$env:PYTHONPATH
  try{$env:PYTHONPATH=$SourceTools;$targetOutput=& $Python -B -m local_hand.bootstrap_safety validate-repository-target --projects-root $ProjectsRoot --repository-path $RepositoryPath;$targetRc=$LASTEXITCODE;if($targetRc -ne 0){throw "repository target identity validation failed"};$TargetRepo=($targetOutput|Out-String).Trim()}finally{if($null -eq $oldPP){Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue}else{$env:PYTHONPATH=$oldPP}}
  $TargetNeedsSeed=-not (Test-Path -LiteralPath (Join-Path $TargetRepo ".git"))
  if($TargetNeedsSeed){
    if([string]::IsNullOrWhiteSpace($SeedRepositoryFrom) -or -not (Test-Path -LiteralPath $SeedRepositoryFrom -PathType Container)){throw "-SeedRepositoryFrom must name a local Git working copy"}
    $SeedRepositoryFrom=(Resolve-Path -LiteralPath $SeedRepositoryFrom).Path
    $seedInside=(Invoke-SafeGit "-C" $SeedRepositoryFrom "rev-parse" "--is-inside-work-tree"|Out-String).Trim();if($LASTEXITCODE -ne 0 -or $seedInside -ne 'true'){throw "seed repository is not a Git working copy"}
    $seedTop=(Invoke-SafeGit "-C" $SeedRepositoryFrom "rev-parse" "--show-toplevel"|Out-String).Trim();if($LASTEXITCODE -ne 0 -or -not [string]::Equals([IO.Path]::GetFullPath($seedTop).TrimEnd('\'),[IO.Path]::GetFullPath($SeedRepositoryFrom).TrimEnd('\'),[StringComparison]::OrdinalIgnoreCase)){throw "seed repository path must be the exact working-copy root"}
    Assert-NoExecutionFilters $SeedRepositoryFrom
  }
  try{$env:PYTHONPATH=$SourceTools;& $Python -B -m local_hand.bootstrap_safety validate-roots --state-root $StateRoot --projects-root $ProjectsRoot;if($LASTEXITCODE -ne 0){throw "StateRoot/ProjectsRoot safety validation failed"}}finally{if($null -eq $oldPP){Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue}else{$env:PYTHONPATH=$oldPP}}

  $oldPP=$env:PYTHONPATH; try{$env:PYTHONPATH=$SourceTools;$ownerOutput=& $Python -B -m local_hand.bootstrap_safety service-owner-token --state-root $StateRoot --node-id $NodeId --service-id $TaskName;$ownerRc=$LASTEXITCODE;if($ownerRc -ne 0){throw "cannot derive Scheduled Task ownership token"};$TaskOwnerToken=($ownerOutput|Out-String).Trim()}finally{if($null -eq $oldPP){Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue}else{$env:PYTHONPATH=$oldPP}}
  $oldPP=$env:PYTHONPATH; try{$env:PYTHONPATH=$SourceTools;$installOutput=& $Python -B -m local_hand.bootstrap_safety new-install-instance-id;$installRc=$LASTEXITCODE;if($installRc -ne 0){throw "cannot derive install instance identity"};$InstallInstanceId=($installOutput|Out-String).Trim()}finally{if($null -eq $oldPP){Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue}else{$env:PYTHONPATH=$oldPP}}
  $TaskOwnerPrefix="Local Hand v0.1 [$TaskOwnerToken]"; $TaskDescription="$TaskOwnerPrefix install=$InstallInstanceId"
  $null=Get-OwnedScheduledTask

  $CredentialsBase=Join-Path $StateRoot "credentials"; $CredentialsRoot=Join-Path $CredentialsBase $InstallInstanceId; $RuntimeState=Join-Path $StateRoot "runtime"; $DeploymentsRoot=Join-Path $StateRoot "deployments"; $MailboxesRoot=Join-Path $StateRoot "mailboxes"; $RunnersRoot=Join-Path $StateRoot "runners"; $RecoveryRoot=Join-Path $StateRoot "recovery"; $RunHome=Join-Path $StateRoot "home"
  $StateRootExisted=Test-Path -LiteralPath $StateRoot
  $markerArgs=@("-m","local_hand.bootstrap_safety","ensure-root-marker","--state-root",$StateRoot,"--node-id",$NodeId,"--service-id",$TaskName);if(-not $StateRootExisted){$markerArgs += "--allow-create"}
  $oldPP=$env:PYTHONPATH; try{$env:PYTHONPATH=$SourceTools;& $Python -B @markerArgs;if($LASTEXITCODE -ne 0){throw "StateRoot ownership marker validation failed"}}finally{if($null -eq $oldPP){Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue}else{$env:PYTHONPATH=$oldPP}}
  $OwnerMarker=Join-Path $StateRoot ".local-hand-root-owner.json"
  $ManagedRoots=@($CredentialsBase,$CredentialsRoot,$RuntimeState,$DeploymentsRoot,$MailboxesRoot,$RunnersRoot,$RecoveryRoot,$ProjectsRoot,$RunHome)
  foreach($root in $ManagedRoots){$oldPP=$env:PYTHONPATH;try{$env:PYTHONPATH=$SourceTools;& $Python -B -m local_hand.bootstrap_safety validate-roots --state-root $StateRoot --projects-root $root;if($LASTEXITCODE -ne 0){throw "managed root safety validation failed: $root"}}finally{if($null -eq $oldPP){Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue}else{$env:PYTHONPATH=$oldPP}}}
  New-Item -ItemType Directory -Force -Path $ManagedRoots|Out-Null
  foreach($root in $ManagedRoots){$oldPP=$env:PYTHONPATH;try{$env:PYTHONPATH=$SourceTools;& $Python -B -m local_hand.bootstrap_safety validate-roots --state-root $StateRoot --projects-root $root;if($LASTEXITCODE -ne 0){throw "managed root became unsafe: $root"}}finally{if($null -eq $oldPP){Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue}else{$env:PYTHONPATH=$oldPP}}}
  Set-RootAcl $StateRoot; Set-ReadOnlyFileAcl $OwnerMarker; Set-ReadOnlyAcl $CredentialsBase; Set-ReadOnlyAcl $CredentialsRoot; Set-ReadOnlyAcl $DeploymentsRoot; Set-ReadOnlyAcl $RunnersRoot; Set-ReadOnlyAcl $RecoveryRoot; Set-ReadOnlyAcl $RunHome
  Set-WritableAcl $RuntimeState; Set-WritableAcl $MailboxesRoot; Set-WritableAcl $ProjectsRoot
  $oldPP=$env:PYTHONPATH; try{$env:PYTHONPATH=$SourceTools;& $Python -B -m local_hand.bootstrap_safety ensure-root-marker --state-root $StateRoot --node-id $NodeId --service-id $TaskName;if($LASTEXITCODE -ne 0){throw "StateRoot ownership marker changed during ACL establishment"}}finally{if($null -eq $oldPP){Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue}else{$env:PYTHONPATH=$oldPP}}

  $MailboxUsesSsh="1"; $MailboxKey=Join-Path $CredentialsRoot "mailbox_id"; $MailboxKnownHosts=Join-Path $CredentialsRoot "known_hosts"
  if([string]::IsNullOrWhiteSpace($MailboxSshKey) -or -not (Test-Path -LiteralPath $MailboxSshKey -PathType Leaf)){throw "-MailboxSshKey required for SSH mailbox URL"}; if([string]::IsNullOrWhiteSpace($KnownHostsFile) -or -not (Test-Path -LiteralPath $KnownHostsFile -PathType Leaf)){throw "-KnownHostsFile required for SSH mailbox URL"}
  $ProvisioningMailboxKey=(Resolve-Path -LiteralPath $MailboxSshKey).Path; $ProvisioningKnownHosts=(Resolve-Path -LiteralPath $KnownHostsFile).Path
  # Bootstrap runs elevated, so its SSH preflight must not use a key whose DACL also names Local Service.
  $env:GIT_SSH_COMMAND="`"$Ssh`" -F NUL -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 -o IdentitiesOnly=yes -o IdentityAgent=none -o PermitLocalCommand=no -o ClearAllForwardings=yes -i `"$ProvisioningMailboxKey`" -o UserKnownHostsFile=`"$ProvisioningKnownHosts`" -o StrictHostKeyChecking=yes"

  $oldPP=$env:PYTHONPATH; try{$env:PYTHONPATH=$SourceTools;& $Python -B -m local_hand.bootstrap_safety validate-roots --state-root $ProjectsRoot --projects-root $TargetRepo;if($LASTEXITCODE -ne 0){throw "target repository root safety validation failed"}}finally{if($null -eq $oldPP){Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue}else{$env:PYTHONPATH=$oldPP}}
  if($TargetNeedsSeed){ Invoke-SafeGit "clone" "--no-local" $SeedRepositoryFrom $TargetRepo|Out-Host; if($LASTEXITCODE -ne 0){throw "scratch repository seed clone failed"} }
  $oldPP=$env:PYTHONPATH; try{$env:PYTHONPATH=$SourceTools;& $Python -B -m local_hand.bootstrap_safety validate-roots --state-root $ProjectsRoot --projects-root $TargetRepo;if($LASTEXITCODE -ne 0){throw "target repository root became unsafe"}}finally{if($null -eq $oldPP){Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue}else{$env:PYTHONPATH=$oldPP}}
  $oldPP=$env:PYTHONPATH; try{$env:PYTHONPATH=$SourceTools;& $Python -B -m local_hand.bootstrap_safety validate-repository-target --projects-root $ProjectsRoot --repository-path $RepositoryPath | Out-Null;if($LASTEXITCODE -ne 0){throw "target repository identity changed during seed"}}finally{if($null -eq $oldPP){Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue}else{$env:PYTHONPATH=$oldPP}}
  Set-WritableAcl $TargetRepo

  $StageRoot=Join-Path ([IO.Path]::GetTempPath()) ("local-hand-stage-"+[guid]::NewGuid().ToString("N")); $StageWorkerRoot=Join-Path $StageRoot "worker"; $StagePackageRoot=Join-Path $StageWorkerRoot "local_hand"; $StageProfile=Join-Path $StageRoot "node-profile.json"; New-Item -ItemType Directory -Force -Path $StagePackageRoot|Out-Null
  $packageFiles=@("__init__.py","protocol.py","paths.py","config.py","provenance.py","installation.py","observe.py","act.py","validate.py","bounded_io.py","git_safety.py","mailbox_safety.py","runtime_lock.py","bootstrap_safety.py","windows_runner.py","worker.py"); foreach($file in $packageFiles){$source=Join-Path $PSScriptRoot $file; if(-not(Test-Path $source -PathType Leaf)){throw "missing Local Hand package file: $source"}; Copy-Item $source (Join-Path $StagePackageRoot $file) -Force}
  Copy-Item -LiteralPath $ProfileSource -Destination $StageProfile
  if((Get-FileHash -Algorithm SHA256 $StageProfile).Hash.ToLowerInvariant() -ne $AdmittedProfileSha){throw 'profile changed after admission'}
  $oldPP=$env:PYTHONPATH;try{$env:PYTHONPATH=$SourceTools;& $Python -B -m local_hand.provenance --stamp $StageWorkerRoot|Out-Null;if($LASTEXITCODE -ne 0){throw 'staged provenance failed'}}finally{if($null -eq $oldPP){Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue}else{$env:PYTHONPATH=$oldPP}}
  $packageFiles += '_build_metadata.json'
  & $Python -m compileall -q $StagePackageRoot; if($LASTEXITCODE -ne 0){throw "staged Local Hand compileall failed"}; $oldPP=$env:PYTHONPATH; try{$env:PYTHONPATH=$StageWorkerRoot; & $Python -c "from pathlib import Path; from local_hand.paths import load_profile,repository_root; from local_hand.worker import _package_digest; import sys; p=load_profile(Path(sys.argv[1])); assert p.node_id and repository_root(p,sys.argv[2]) and len(_package_digest())==64" $StageProfile $RepositoryName; if($LASTEXITCODE -ne 0){throw "staged Local Hand import/profile/repository validation failed"}}finally{if($null -eq $oldPP){Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue}else{$env:PYTHONPATH=$oldPP}}

  $ProfileSha=(Get-FileHash -Algorithm SHA256 $StageProfile).Hash.ToLowerInvariant(); $DeploymentId="$ImplementationCommit-$($ProfileSha.Substring(0,12))"; $DeploymentRoot=Join-Path $DeploymentsRoot $DeploymentId
  if(Test-Path $DeploymentRoot){
    foreach($relative in @("node-profile.json")+($packageFiles|ForEach-Object{"worker\local_hand\$_"})){$a=Join-Path $StageRoot $relative;$b=Join-Path $DeploymentRoot $relative;if(-not(Test-Path $b -PathType Leaf)){throw "existing immutable deployment missing: $relative"};if((Get-FileHash -Algorithm SHA256 $a).Hash -ne (Get-FileHash -Algorithm SHA256 $b).Hash){throw "existing immutable deployment mismatch: $relative"}}
  } else {
    New-Item -ItemType Directory -Force -Path (Join-Path $DeploymentRoot "worker\local_hand")|Out-Null
    foreach($file in $packageFiles){Copy-Item (Join-Path $StagePackageRoot $file) (Join-Path $DeploymentRoot "worker\local_hand\$file") -Force}
    Copy-Item $StageProfile (Join-Path $DeploymentRoot "node-profile.json") -Force
    $DeploymentCreated=$true
  }
  Set-ReadOnlyAcl $DeploymentRoot
  $WorkerRoot=Join-Path $DeploymentRoot "worker"; $ProfilePath=Join-Path $DeploymentRoot "node-profile.json"

  $MailboxRoot=Join-Path $MailboxesRoot $InstallInstanceId
  Invoke-SafeGit "clone" "--depth=1" "--filter=blob:limit=8388608" "--no-checkout" "--origin" "origin" "--single-branch" "--branch" $MailboxBranch $MailboxUrl $MailboxRoot|Out-Host; if($LASTEXITCODE -ne 0){throw "staged mailbox clone failed"}
  Set-WritableAcl $MailboxRoot
  $oldPP=$env:PYTHONPATH; try{$env:PYTHONPATH=$WorkerRoot; & $Python -c "from pathlib import Path; from local_hand.git_safety import assert_no_execution_filters,sanitized_git_env; from local_hand.mailbox_safety import admit_remote_tree; import sys; r=Path(sys.argv[1]); assert_no_execution_filters(r,sanitized_git_env()); admit_remote_tree(r,sys.argv[2])" $MailboxRoot "origin/$MailboxBranch"; if($LASTEXITCODE -ne 0){throw "mailbox tree admission failed"}}finally{if($null -eq $oldPP){Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue}else{$env:PYTHONPATH=$oldPP}}
  Assert-NoExecutionFilters $MailboxRoot
  Invoke-SafeGit "-C" $MailboxRoot "sparse-checkout" "init" "--no-cone"|Out-Null
  Invoke-SafeGit "-C" $MailboxRoot "sparse-checkout" "set" "--no-cone" "/_executor_spike/tasks/" "/_executor_spike/results/" "/_executor_spike/conflicts/"|Out-Null
  $oldNoLazy=$env:GIT_NO_LAZY_FETCH; try{$env:GIT_NO_LAZY_FETCH="1";Invoke-SafeGit "-C" $MailboxRoot "reset" "--hard" "origin/$MailboxBranch"|Out-Host;if($LASTEXITCODE -ne 0){throw "staged mailbox checkout failed"}}finally{if($null -eq $oldNoLazy){Remove-Item Env:GIT_NO_LAZY_FETCH -ErrorAction SilentlyContinue}else{$env:GIT_NO_LAZY_FETCH=$oldNoLazy}}
  $oldPP=$env:PYTHONPATH; try{$env:PYTHONPATH=$WorkerRoot;& $Python -c "from pathlib import Path; from local_hand.mailbox_safety import validate_checkout_control_dirs; import sys; validate_checkout_control_dirs(Path(sys.argv[1]))" $MailboxRoot;if($LASTEXITCODE -ne 0){throw "staged mailbox path confinement failed"}}finally{if($null -eq $oldPP){Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue}else{$env:PYTHONPATH=$oldPP}}
  foreach($relative in @("","_executor_spike","_executor_spike\tasks","_executor_spike\results","_executor_spike\conflicts")){
    $controlPath=if([string]::IsNullOrEmpty($relative)){$MailboxRoot}else{Join-Path $MailboxRoot $relative}
    if(-not(Test-Path -LiteralPath $controlPath -PathType Container)){throw "mailbox control directory missing before ACL normalization: $controlPath"}
    Set-WritableAcl $controlPath
  }

  # Materialize the service-facing copy only after the elevated mailbox admission succeeds.
  Copy-Item $ProvisioningMailboxKey $MailboxKey -Force; Copy-Item $ProvisioningKnownHosts $MailboxKnownHosts -Force
  Set-RuntimePrivateKeyAcl $MailboxKey; Set-ReadOnlyFileAcl $MailboxKnownHosts
  $env:GIT_SSH_COMMAND="`"$Ssh`" -F NUL -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 -o IdentitiesOnly=yes -o IdentityAgent=none -o PermitLocalCommand=no -o ClearAllForwardings=yes -i `"$MailboxKey`" -o UserKnownHostsFile=`"$MailboxKnownHosts`" -o StrictHostKeyChecking=yes"

  $RunnerPath=Join-Path $RunnersRoot ("$InstallInstanceId.ps1")
  $InstallRecord=Join-Path $CredentialsRoot 'install-record.json'
  $oldPP=$env:PYTHONPATH;try{$env:PYTHONPATH=$WorkerRoot;& $Python -B -m local_hand.installation --profile $ProfilePath --output $InstallRecord --state-root $RuntimeState --mailbox-root $MailboxRoot --install-instance-id $InstallInstanceId --git $Git --ssh $Ssh --mailbox-key $MailboxKey --known-hosts $MailboxKnownHosts|Out-Null;if($LASTEXITCODE -ne 0){throw 'installation record binding failed'}}finally{if($null -eq $oldPP){Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue}else{$env:PYTHONPATH=$oldPP}}
  Set-ReadOnlyFileAcl $InstallRecord
  $runnerArgs=@("-m","local_hand.windows_runner","--output",$RunnerPath,"--home",$RunHome,"--worker-root",$WorkerRoot,"--profile",$ProfilePath,"--mailbox",$MailboxRoot,"--branch",$MailboxBranch,"--runtime",$RuntimeState,"--python",$Python,"--git",$Git,"--ssh",$Ssh,"--commit",$ImplementationCommit,"--install-instance-id",$InstallInstanceId,"--install-record",$InstallRecord,"--mailbox-uses-ssh",$MailboxUsesSsh,"--mailbox-key",$MailboxKey,"--known-hosts",$MailboxKnownHosts)
  $oldPP=$env:PYTHONPATH; try{$env:PYTHONPATH=$SourceTools;& $Python -B @runnerArgs;if($LASTEXITCODE -ne 0){throw "failed to render Windows worker runner"}}finally{if($null -eq $oldPP){Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue}else{$env:PYTHONPATH=$oldPP}}

  $sourceDirtyAfterPreparation=(Invoke-SafeGit "-C" $repoRoot "status" "--porcelain=v1" "--untracked-files=all" "--" "tools/local_hand"|Out-String).Trim()
  if(-not [string]::IsNullOrWhiteSpace($sourceDirtyAfterPreparation)){throw "tools/local_hand source tree became dirty during bootstrap preparation"}

  $action=New-ScheduledTaskAction -Execute $PowerShell -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$RunnerPath`""; $trigger=New-ScheduledTaskTrigger -AtStartup; $settings=New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero); $principal=New-ScheduledTaskPrincipal -UserId $TaskPrincipalUser -LogonType ServiceAccount -RunLevel Limited
  $old=Get-OwnedScheduledTask; $oldXml=$null; $oldRunning=$false
  if($null -ne $old){
    $oldXml=Export-ScheduledTask -TaskPath '\' -TaskName $TaskName; $oldRunning=($old.State -eq 'Running')
    $RecoveryInstanceRoot=Join-Path $RecoveryRoot $InstallInstanceId
    New-Item -ItemType Directory -Path $RecoveryInstanceRoot|Out-Null; Set-ReadOnlyAcl $RecoveryInstanceRoot
    $RecoveryXmlPath=Join-Path $RecoveryInstanceRoot "previous-task.xml"
    $utf8NoBom=[Text.UTF8Encoding]::new($false); $recoveryStream=[IO.FileStream]::new($RecoveryXmlPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try{$bytes=$utf8NoBom.GetBytes($oldXml);$recoveryStream.Write($bytes,0,$bytes.Length);$recoveryStream.Flush($true)}finally{$recoveryStream.Dispose()}
    Set-ReadOnlyFileAcl $RecoveryXmlPath
  }
  try {
    $SwitchStarted=$true
    if($null -ne $old -and $oldRunning){Stop-ScheduledTask -TaskPath '\' -TaskName $TaskName;$deadline=(Get-Date).AddSeconds(10);do{Start-Sleep -Milliseconds 200;$s=(Get-ScheduledTask -TaskPath '\' -TaskName $TaskName).State}while($s -eq 'Running' -and (Get-Date)-lt $deadline);if($s -eq 'Running'){throw "old Local Hand task did not stop before upgrade"}}
    Register-ScheduledTask -TaskPath '\' -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description $TaskDescription -Force|Out-Null
    Start-ScheduledTask -TaskPath '\' -TaskName $TaskName; $deadline=(Get-Date).AddSeconds(10);$running=$false;do{Start-Sleep -Milliseconds 250;$cur=Get-ScheduledTask -TaskPath '\' -TaskName $TaskName;if($cur.State -eq 'Running'){$running=$true;break}}while((Get-Date)-lt $deadline);if(-not $running){throw "new Local Hand Scheduled Task failed running-state health check"};Start-Sleep -Seconds 3;if((Get-ScheduledTask -TaskPath '\' -TaskName $TaskName).State -ne 'Running'){throw "new Local Hand Scheduled Task did not remain running through stabilization window"}
    $SwitchCommitted=$true
  } catch {
    $e=$_; $rollbackError=$null
    try {
      Stop-ScheduledTask -TaskPath '\' -TaskName $TaskName -ErrorAction SilentlyContinue
      $deadline=(Get-Date).AddSeconds(10);do{Start-Sleep -Milliseconds 200;$newTask=Get-ScheduledTask -TaskPath '\' -TaskName $TaskName -ErrorAction SilentlyContinue;$newState=if($null -eq $newTask){'Absent'}else{$newTask.State}}while($newState -eq 'Running' -and (Get-Date)-lt $deadline)
      if($newState -eq 'Running'){$UnsafeLiveProcess=$true;throw "new Local Hand task did not stop during rollback; old task not restarted"}
      if($null -ne $oldXml){
        Register-ScheduledTask -TaskPath '\' -TaskName $TaskName -Xml $oldXml -Force|Out-Null
        if($oldRunning){Start-ScheduledTask -TaskPath '\' -TaskName $TaskName;$deadline=(Get-Date).AddSeconds(10);do{Start-Sleep -Milliseconds 200;$restored=Get-ScheduledTask -TaskPath '\' -TaskName $TaskName}while($restored.State -ne 'Running' -and (Get-Date)-lt $deadline)}else{$restored=Get-ScheduledTask -TaskPath '\' -TaskName $TaskName}
        if($null -eq $restored -or $restored.Description -ne $old.Description){throw "previous Local Hand task identity was not restored"}
        if($oldRunning -and $restored.State -ne 'Running'){throw "previous Local Hand task running state was not restored"}
        if(-not $oldRunning -and $restored.State -eq 'Running'){throw "previous Local Hand task stopped state was not restored"}
      } else {
        $newTask=Get-ScheduledTask -TaskPath '\' -TaskName $TaskName -ErrorAction SilentlyContinue
        if($null -ne $newTask){Unregister-ScheduledTask -TaskPath '\' -TaskName $TaskName -Confirm:$false -ErrorAction Stop}
        if($null -ne (Get-ScheduledTask -TaskPath '\' -TaskName $TaskName -ErrorAction SilentlyContinue)){throw "new Local Hand task registration was not removed"}
      }
    } catch {
      $RollbackFailed=$true; $rollbackError=$_
    }
    if($RollbackFailed){$recoveryHint=if($null -ne $RecoveryXmlPath){" previous XML preserved at $RecoveryXmlPath"}else{" new instance artifacts preserved"};throw "Local Hand switch failed: $($e.Exception.Message); rollback could not be verified: $($rollbackError.Exception.Message);$recoveryHint"}
    throw $e
  }

  $Succeeded=$true
  Write-Output "BOOTSTRAP=PASS";Write-Output "NODE_ID=$NodeId";Write-Output "SERVICE_ACCOUNT=$ServiceAccount";Write-Output "STATE_ROOT=$StateRoot";Write-Output "PROJECTS_ROOT=$ProjectsRoot";Write-Output "PROFILE=$ProfilePath";Write-Output "MAILBOX=$MailboxRoot";Write-Output "DEPLOYMENT_ID=$DeploymentId";Write-Output "INSTALL_INSTANCE_ID=$InstallInstanceId";Write-Output "IMPLEMENTATION_COMMIT=$ImplementationCommit";Write-Output "SOURCE_HEAD_VERIFIED=$ActualSourceHead";Write-Output "SOURCE_TREE_CLEAN=true";Write-Output "TASK_RUNNING=true";Write-Output "DEDICATED_OS_IDENTITY=true";Write-Output "IMMUTABLE_DEPLOYMENT=true";Write-Output "INDEPENDENT_MAILBOX=true";Write-Output "VALIDATION_PROFILE_ADMITTED=true";Write-Output "SINGLE_WRITER=$([bool]$ProfileSettings.single_writer)"
} finally {
  if(-not $Succeeded -and -not $UnsafeLiveProcess -and -not $RollbackFailed -and -not $SwitchCommitted){
    if($null -ne $MailboxRoot -and (Test-Path $MailboxRoot)){Remove-Item $MailboxRoot -Recurse -Force -ErrorAction SilentlyContinue}
    if($null -ne $RunnerPath -and (Test-Path $RunnerPath)){Remove-Item $RunnerPath -Force -ErrorAction SilentlyContinue}
    if($null -ne $CredentialsRoot -and (Test-Path $CredentialsRoot)){Remove-Item $CredentialsRoot -Recurse -Force -ErrorAction SilentlyContinue}
    if($DeploymentCreated -and $null -ne $DeploymentRoot -and (Test-Path $DeploymentRoot)){Remove-Item $DeploymentRoot -Recurse -Force -ErrorAction SilentlyContinue}
  }
  if(-not $UnsafeLiveProcess -and -not $RollbackFailed -and $null -ne $RecoveryInstanceRoot -and (Test-Path $RecoveryInstanceRoot)){Remove-Item $RecoveryInstanceRoot -Recurse -Force -ErrorAction SilentlyContinue}
  if($null -ne $StageRoot -and (Test-Path $StageRoot)){Remove-Item $StageRoot -Recurse -Force -ErrorAction SilentlyContinue}
  Remove-Item $DisabledHooks -Recurse -Force -ErrorAction SilentlyContinue
}
