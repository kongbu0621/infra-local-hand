function Get-LocalHandAclRuleKeys([System.Security.AccessControl.FileSystemSecurity]$Acl) {
    return @($Acl.Access | ForEach-Object {
        $sid=$_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
        "$sid|$($_.AccessControlType)|$([int]$_.FileSystemRights)|$([int]$_.InheritanceFlags)|$([int]$_.PropagationFlags)|$($_.IsInherited)"
    } | Sort-Object)
}

function New-LocalHandAclRule(
    [string]$Sid,
    [System.Security.AccessControl.FileSystemRights]$Rights,
    [System.Security.AccessControl.InheritanceFlags]$InheritanceFlags
) {
    $identity=[System.Security.Principal.SecurityIdentifier]::new($Sid)
    return [System.Security.AccessControl.FileSystemAccessRule]::new(
        $identity,
        $Rights,
        $InheritanceFlags,
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
}

function Set-LocalHandExactDirectoryAcl(
    [string]$Path,
    [System.Security.AccessControl.FileSystemRights]$LocalServiceRights,
    [bool]$InheritToChildren
) {
    $acl=Get-Acl -LiteralPath $Path
    $acl.SetAccessRuleProtection($true,$false)
    foreach($rule in @($acl.Access)){[void]$acl.RemoveAccessRuleSpecific($rule)}
    $inheritance=if($InheritToChildren){
        [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    }else{
        [System.Security.AccessControl.InheritanceFlags]::None
    }
    foreach($entry in @(
        @('S-1-5-18',[System.Security.AccessControl.FileSystemRights]::FullControl),
        @('S-1-5-32-544',[System.Security.AccessControl.FileSystemRights]::FullControl),
        @('S-1-5-19',$LocalServiceRights)
    )){
        [void]$acl.AddAccessRule((New-LocalHandAclRule $entry[0] $entry[1] $inheritance))
    }
    $expected=Get-LocalHandAclRuleKeys $acl
    Set-Acl -LiteralPath $Path -AclObject $acl
    $actualAcl=Get-Acl -LiteralPath $Path
    $actual=Get-LocalHandAclRuleKeys $actualAcl
    if(-not $actualAcl.AreAccessRulesProtected -or $null -ne (Compare-Object $expected $actual)){
        throw "exact Local Hand directory ACL verification failed: $Path"
    }
}

function Set-LocalHandExactFileAcl(
    [string]$Path,
    [System.Security.AccessControl.FileSystemRights]$LocalServiceRights
) {
    $acl=Get-Acl -LiteralPath $Path
    $acl.SetAccessRuleProtection($true,$false)
    foreach($rule in @($acl.Access)){[void]$acl.RemoveAccessRuleSpecific($rule)}
    foreach($entry in @(
        @('S-1-5-18',[System.Security.AccessControl.FileSystemRights]::FullControl),
        @('S-1-5-32-544',[System.Security.AccessControl.FileSystemRights]::FullControl),
        @('S-1-5-19',$LocalServiceRights)
    )){
        [void]$acl.AddAccessRule((New-LocalHandAclRule $entry[0] $entry[1] ([System.Security.AccessControl.InheritanceFlags]::None)))
    }
    $expected=Get-LocalHandAclRuleKeys $acl
    Set-Acl -LiteralPath $Path -AclObject $acl
    $actualAcl=Get-Acl -LiteralPath $Path
    $actual=Get-LocalHandAclRuleKeys $actualAcl
    if(-not $actualAcl.AreAccessRulesProtected -or $null -ne (Compare-Object $expected $actual)){
        throw "exact Local Hand file ACL verification failed: $Path"
    }
}

function Set-LocalHandRuntimePrivateKeyAcl([string]$Path) {
    # Win32-OpenSSH accepts a private-key owner of Administrators and ACEs for
    # Administrators, SYSTEM, and the current (Local Service) runtime identity.
    $administrators=[System.Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
    $acl=Get-Acl -LiteralPath $Path
    $acl.SetOwner($administrators)
    $acl.SetAccessRuleProtection($true,$false)
    foreach($rule in @($acl.Access)){[void]$acl.RemoveAccessRuleSpecific($rule)}
    foreach($entry in @(
        @('S-1-5-18',[System.Security.AccessControl.FileSystemRights]::FullControl),
        @('S-1-5-32-544',[System.Security.AccessControl.FileSystemRights]::FullControl),
        @('S-1-5-19',[System.Security.AccessControl.FileSystemRights]::Read)
    )){
        [void]$acl.AddAccessRule((New-LocalHandAclRule $entry[0] $entry[1] ([System.Security.AccessControl.InheritanceFlags]::None)))
    }
    $expected=Get-LocalHandAclRuleKeys $acl
    Set-Acl -LiteralPath $Path -AclObject $acl
    $actualAcl=Get-Acl -LiteralPath $Path
    $actualOwner=$actualAcl.Owner
    try{$actualOwner=[System.Security.Principal.NTAccount]::new($actualOwner).Translate([System.Security.Principal.SecurityIdentifier]).Value}catch{
        try{$actualOwner=[System.Security.Principal.SecurityIdentifier]::new($actualOwner).Value}catch{throw "cannot resolve Local Hand private-key owner: $Path"}
    }
    $actual=Get-LocalHandAclRuleKeys $actualAcl
    if(
        $actualOwner -ne $administrators.Value -or
        -not $actualAcl.AreAccessRulesProtected -or
        $null -ne (Compare-Object $expected $actual)
    ){
        throw "exact Local Hand private-key owner/DACL verification failed: $Path"
    }
}
