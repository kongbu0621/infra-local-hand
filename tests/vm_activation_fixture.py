"""Synthetic successful activation originals; no machine paths or live operations."""
import json
from e3_host import q2_core_prior_attempt as p

def records(anchor='/fixture', historical_boot='11111111-2222-3333-4444-555555555555'):
    dump=lambda v:json.dumps(v,sort_keys=True,separators=(',',':')).encode()
    sha=p.c.sha256
    files={name:b'' for name in p.ACTIVATION_FILES}
    event=p.ACTIVATION_EVENT;boot='33333333-2222-3333-4444-555555555555'
    pidfile='/activation/vm.pid';serial='/activation/serial';system='/candidate/system-repaired.qcow2'
    argv=['qemu-system-x86_64','-serial','file:'+serial,'-pidfile',pidfile,'-drive','if=none,id=os,format=qcow2,file='+system]
    vm=dict(pid=123,starttime=1,argv_sha256=sha(dump(argv)))
    package=dict(Package='linux-modules-extra-fixture',Version='1.0',Filename='pool/modules.deb')
    proposal=dict(package=package,reconcile_script_sha256='e'*64,candidate=dict(candidate_path=system,candidate_sha256='a'*64),
        minimal_change=dict(full_argv=argv,new_pidfile=pidfile,new_serial=serial,system_drive_file=system))
    files['activation-proposal-private.json']=dump(proposal)
    files['activate-approved.py']=b"LOADER = \"base='/fixture/staged-package'\\n\"\n"
    authority=dict(event=event,state='APPROVED',approved_action='ACTIVATE_EXACT_PROPOSAL_ONCE',owner_reply='approved synthetic only',
        startup_calls=1,ssh_calls=1,retries=0,stop_or_kill_calls=0,proposal_sha256=sha(files['activation-proposal-private.json']),helper_sha256=sha(files['activate-approved.py']))
    files['explicit-owner-approval-private.json']=dump(authority)
    frozen=dict(event=event,authority_sha256=sha(files['explicit-owner-approval-private.json']),proposal_sha256=authority['proposal_sha256'],helper_sha256=authority['helper_sha256'])
    files['execution-freeze-private.json']=dump(frozen)
    files['launch-consumed-private.json']=dump(dict(frozen,argv=argv))
    files['ssh-consumed-private.json']=dump(dict(event=event,new_vm=vm,script_sha256=proposal['reconcile_script_sha256']))
    quota=dict(filesystems=[dict(fstype='ext4',options='rw,nodev,nosuid,noexec,prjquota')])
    labels=['modules-dependency','regdb-dependency','quota-mount','module-vermagic','install-exact-local-package','installed-package','package-integrity','module-resolution','quota-mount-after']
    steps=[dict(label=label,exit=0,argv=[],stdout='') for label in labels]
    steps[2]['stdout']=steps[8]['stdout']=dump(quota).decode()
    steps[4]['argv']=['dpkg','--install','/fixture/staged-package/modules.deb']
    steps[5].update(argv=['dpkg-query','-W','-f=${Status}\t${Version}',package['Package']],stdout='install ok installed\t1.0')
    steps[6]['argv']=['dpkg','--verify',package['Package']]
    guest=dict(state='EXACT_PACKAGE_INSTALLED_QUOTA_MOUNT_VERIFIED',package_install_calls=1,network_package_calls=0,reboots=0,boot=boot,steps=steps)
    files['ssh-install.stdout']=dump(guest)
    oldimages={role:dict(metadata=dict(dev=1,ino=i+10)) for i,role in enumerate(('system','quota','journal','evidence','seed'))}
    oldimages['system']['metadata']['ino']=9
    candidate=dict(metadata=dict(dev=1,ino=10))
    result=dict(event=event,state='ACTIVATED_EXACT_PACKAGE_INSTALLED_QUOTA_VERIFIED',startup_calls=1,ssh_calls=1,package_install_calls=1,
        automatic_retries=0,stop_calls=0,errors=[],guest_completion='VERIFIED',original_system_and_old_outputs_preserved=True,
        guest_boot=boot,new_vm=vm,host_boot='44444444-2222-3333-4444-555555555555',original_images_before=oldimages,candidate_before=candidate,
        commands=[dict(label=label,returncode=0,eof=True) for label in ('qemu-version','endpoint-before','qemu-start','endpoint-after','ssh-install')])
    files['result-private.json']=dump(result)
    binding=dict(event=event,new_vm=vm,qemu_argv=argv,pidfile=pidfile,serial=serial,active_system_path=system,host_boot=result['host_boot'],guest_boot=boot,
        no_replay_or_new_execution_permission=True,installed_package=package['Package'],installed_package_version=package['Version'],
        original_system_preserved=oldimages['system'],active_system_prelaunch_metadata=candidate,active_system_prelaunch_sha256=proposal['candidate']['candidate_sha256'])
    for key,name in (('authority','explicit-owner-approval-private.json'),('launch_marker','launch-consumed-private.json'),('ssh_marker','ssh-consumed-private.json'),('source_guest_stdout','ssh-install.stdout'),('source_result','result-private.json')):
        binding[key]=dict(name=name,bytes=len(files[name]),sha256=sha(files[name]))
    files['current-vm-binding-private.json']=dump(binding)
    files['new-pid-cmdline.raw']=b'\0'.join(word.encode() for word in argv)+b'\0'
    files['new-pid-stat.raw']=b'123 (qemu) S '+b'0 '*18+b'1\n'
    return files,index(files),historical_boot

def index(files):
    return p.c.canonical(dict(event=p.ACTIVATION_EVENT,state='ACTIVATED_EXACT_PACKAGE_INSTALLED_QUOTA_VERIFIED',
        files=[dict(name=name,bytes=len(raw),sha256=p.c.sha256(raw)) for name,raw in sorted(files.items())]))
