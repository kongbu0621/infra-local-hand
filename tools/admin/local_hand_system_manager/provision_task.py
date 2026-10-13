"""Provision an independent task from one protected installation template.

Reuse the verified quota/chain assembly and existing per-task budgets. Only
server-generated paths, quota IDs and task identities enter the provisioner.
No job is submitted by this component.
"""
from __future__ import annotations
import copy, fcntl, hashlib, importlib.util, json, os, stat, struct, subprocess, sys, time, uuid
from pathlib import Path
from local_hand_jobs import budget, cli, quota_contract as q
from local_hand_jobs.deployment import verify_release
from admin.local_hand_quota_observer.protected_inputs import read_protected

def task_input(config, operation, principal, serial):
    """Refresh boot/cgroup observations and allocate names within fixed roots."""
    v = copy.deepcopy(config['template'])
    plan = v['plan']
    installation = config['installation']
    v['installation'] = installation
    plan['candidate'] = installation['source']
    token = uuid.UUID(operation).hex
    suffix = 'task-' + token + '-' + str(serial)
    replacements = {old: str(Path(new) / suffix) for (old, new) in config['bases'].items()}

    def relocate(value):
        if isinstance(value, str):
            for (old, new) in replacements.items():
                if value == old or value.startswith(old + '/'):
                    return new + value[len(old):]
        if isinstance(value, dict):
            return {k: relocate(x) for (k, x) in value.items()}
        if isinstance(value, list):
            return [relocate(x) for x in value]
        return value
    plan = relocate(plan)
    v['plan'] = plan
    v['bases'] = sorted(replacements.values())
    host = plan['host']
    if Path('/proc/sys/kernel/hostname').read_text().strip() != host['hostname'] or Path('/sys/class/dmi/id/sys_vendor').read_text().strip() != host['dmi_vendor'] or Path('/sys/class/dmi/id/product_name').read_text().strip() != host['dmi_product']:
        raise ValueError('PROVISION_HOST_IDENTITY')
    host['boot_id'] = budget.current_clock()['boot_id']
    ns = os.stat('/proc/self/ns/user')
    host['initial_userns'] = dict(device=ns.st_dev, inode=ns.st_ino)
    observed = v['observed']
    observed['host'] = host
    observed['installation'] = installation
    for (name, old) in observed['parents'].items():
        path = Path('/sys/fs/cgroup' + old['path'])
        info = path.stat()
        if 'populated 0' not in (path / 'cgroup.events').read_text():
            raise ValueError('PROVISION_EXECUTION_BUSY')
        observed['parents'][name] = dict(path=old['path'], device=info.st_dev, inode=info.st_ino)
    for (name, old) in observed['system_geometry'].items():
        if name == 'schema':
            continue
        path = Path('/sys/fs/cgroup' + old['parent']['path'])
        info = path.stat()
        (quota, period) = (path / 'cpu.max').read_text().split()
        measured = dict(memory_bytes=int((path / 'memory.max').read_text()), memory_swap_max=int((path / 'memory.swap.max').read_text()), tasks_max=int((path / 'pids.max').read_text()), cpu_quota_per_sec_usec=int(quota) * 1000000 // int(period))
        if any((measured[k] != old[k] for k in measured)):
            raise ValueError('PROVISION_PARENT_LIMIT_CHANGED')
        old['parent'].update(device=info.st_dev, inode=info.st_ino)
    plan['retained_ordinary_parent'] = observed['system_geometry']['retained_ordinary_parent']['parent']
    for mount_pin in config['mounts']:
        expected_device = os.stat('/dev/disk/by-uuid/' + mount_pin['uuid']).st_rdev
        if (os.stat(mount_pin['source']).st_rdev != expected_device
                or os.stat(mount_pin['path']).st_dev != expected_device):
            raise ValueError('PROVISION_FILESYSTEM_CHANGED')
    mount = plan['mounts']['quota']
    device = os.stat('/dev/disk/by-uuid/' + mount['uuid']).st_rdev
    if os.stat(mount['source']).st_rdev != device or os.stat(mount['path']).st_dev != device:
        raise ValueError('PROVISION_QUOTA_FILESYSTEM_CHANGED')
    mount['device'] = device
    for root in config['bases'].values():
        info = os.statvfs(root)
        if info.f_bavail * info.f_frsize < config['minimum_free_bytes'] or info.f_favail < 4096:
            raise ValueError('PROVISION_FREE_CAPACITY')
    ident = plan['settings']['identity']
    preparation = uuid.uuid4().hex
    ident.update(id=preparation, operation_id=operation, authority_id='lhsvc-' + preparation, ledger_id='lhsvc-' + preparation, profile_ref=config['profile_ref'], install_uuid=config['install_uuid'], epoch=uuid.uuid4().hex, slot_generation=uuid.uuid4().hex, expires_at=int(time.time()) + config['request_ttl_seconds'], session=os.urandom(32).hex, principal_id=principal)
    plan['preparation_id'] = preparation
    for (key, suffix) in (('target', ''), ('supervisor', '-supervisor')):
        plan['settings']['controllers'][key]['unit'] = 'lhqsvc' + token + 'a' + str(serial) + suffix + '.service'
    for (index, root) in enumerate(plan['roots']):
        root['project_id'] = config['first_project_id'] + (serial - 1) * 7 + index
    v.update(transport='broker', mcp=None, cancellation=False, scopes=['lh:inspect', 'lh:submit', 'lh:read', 'lh:evidence'])
    v.pop('helpers', None)
    v.pop('auth', None)
    return v

def _helper(installation, name):
    relative = 'tests/e3_host/' + name + '.py'
    path = Path(installation['source']['root']) / relative
    raw = read_protected(str(path), 2 * 1024 ** 2)
    if hashlib.sha256(raw).hexdigest() != installation['source']['files'].get(relative):
        raise ValueError('PROVISION_SOURCE_CHANGED')
    spec = importlib.util.spec_from_file_location('provision_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def prepare(v):
    plan = copy.deepcopy(v['plan'])
    installation = v['installation']
    if os.geteuid() != 0 or budget.current_clock()['boot_id'] != plan['host']['boot_id']:
        raise ValueError('PROVISION_HOST_CHANGED')
    verify_release(expected_source_commit=installation['source']['commit'], expected_payload_digest=installation['installed']['payload_digest'], expected_entrypoint=installation['installed']['package_root'] + '/local_hand_jobs/cli.py', actual_entrypoint=cli.__file__)
    deadline = time.monotonic() + 60
    quota_module = _helper(installation, 'q2_prepare')
    driver = _helper(installation, 'q2_prepare_driver')
    a = _helper(installation, 'q2_prepare_assembly')
    driver.validate_plan(plan)

    def guard():
        q.require(time.monotonic() < deadline, 'PROVISION_DEADLINE')

    def save(path, value, mode=0o600, uid=0, gid=0):
        raw = json.dumps(value, sort_keys=True, separators=(',', ':')).encode() + b'\n' if not isinstance(value, bytes) else value
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
        try:
            os.fchown(fd, uid, gid)
            os.fchmod(fd, mode)
            pending = memoryview(raw)
            while pending:
                count = os.write(fd, pending)
                q.require(count > 0, 'PROVISION_RECORD_WRITE')
                pending = pending[count:]
            os.fsync(fd)
        finally:
            os.close(fd)
        parent = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(parent)
        finally: os.close(parent)

    def directory(path, uid=0, gid=0, mode=0o755):
        guard()
        p = Path(path)
        for parent in reversed(p.parents):
            s = parent.lstat()
            q.require(stat.S_ISDIR(s.st_mode) and not s.st_mode & 0o022, 'PROVISION_PARENT_PROTECTION')
        q.require(not os.path.lexists(p), 'PROVISION_DIRECTORY_OCCUPIED')
        p.mkdir(mode=mode)
        os.chown(p, uid, gid)
        os.chmod(p, mode)
        parent = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(parent)
        finally: os.close(parent)
        s = p.stat()
        return dict(path=str(p), device=s.st_dev, inode=s.st_ino, uid=s.st_uid, gid=s.st_gid, mode=s.st_mode)

    def pin(p):
        return {k: p[k] for k in ('path', 'device', 'inode')}
    parents = {k: {field: value[field] for field in ('path', 'device', 'inode')} for (k, value) in v['observed']['parents'].items()}
    for (k, p) in parents.items():
        root = Path('/sys/fs/cgroup' + p['path'])
        s = root.stat()
        q.require((s.st_dev, s.st_ino) == (p['device'], p['inode']) and
                  'populated 0' in (root / 'cgroup.events').read_text(), 'PROVISION_PARENT_BUSY_OR_CHANGED')
    for p in v['bases']:
        directory(p)
    dirs = {}
    for name in ['reservation'] + [name for name in plan['directories'] if name != 'reservation']:
        info = plan['directories'][name]
        uid = plan['account']['uid'] if info['owner'] == 'ordinary' else 0
        dirs[name] = directory(info['path'], uid, plan['account']['gid'] if uid else 0, info['mode'])
    reservation = Path(dirs['reservation']['path'])
    save(reservation / 'preparation-plan.json', plan)
    for name in ('setpriv',):
        q.require(hashlib.sha256(Path(plan['tools'][name]['path']).read_bytes()).hexdigest() == plan['tools'][name]['sha256'], 'PROVISION_PROGRAM_CHANGED')
    quota = quota_module.Quota(plan['mounts']['quota']['source'])
    before = quota.inventory(guard)
    for root in plan['roots']:
        quota.unused(root['project_id'])
    sequence = 0

    def event(kind, value):
        nonlocal sequence
        sequence += 1
        save(reservation / (str(sequence) + '-' + kind + '.json'), value)

    def command(argv, **kwargs):
        guard()
        result = subprocess.run(argv, capture_output=True, timeout=min(20, max(0.1, deadline - time.monotonic())), env=quota_module.ENV, cwd='/')
        event('command', dict(argv=argv, returncode=result.returncode, stdout=result.stdout.decode(errors='replace'), stderr=result.stderr.decode(errors='replace')))
        q.require(result.returncode == 0, 'PROVISION_CHILD_FAILED')
        return result.stdout
    roots = []
    for root in plan['roots']:
        quota.unused(root['project_id'])
        event('quota-intent', root)
        created = directory(root['path'], plan['account']['uid'], plan['account']['gid'], 0o700)
        fd = os.open(root['path'], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            attrs = list(struct.unpack('=IIIII8s', fcntl.ioctl(fd, 0x801c581f, bytes(28))))
            q.require(attrs[3] == 0, 'PROVISION_PROJECT_OCCUPIED')
            attrs[0] |= 512
            attrs[3] = root['project_id']
            fcntl.ioctl(fd, 0x401c5820, struct.pack('=IIIII8s', *attrs))
            prior = quota.block(root['project_id'])
            q.require(prior['inodes'] == 1 and all(prior[k] == 0 for k in ('hard', 'soft', 'ihard', 'isoft', 'btime', 'itime')), 'PROVISION_PROJECT_CHANGED')
            limits = quota.Block()
            limits.hard = root['hard_bytes'] // 1024
            limits.ihard = root['inode_hard_limit']
            limits.valid = 5
            quota.call(0x800008, root['project_id'], limits)
            os.fsync(fd)
            attrs = struct.unpack('=IIIII8s', fcntl.ioctl(fd, 0x801c581f, bytes(28)))
            actual = quota.block(root['project_id'])
            q.require(attrs[3] == root['project_id'] and attrs[0] & 512 and actual['hard'] * 1024 == root['hard_bytes'] and actual['ihard'] == root['inode_hard_limit'] and quota.enforcement() & 48 == 48, 'PROVISION_QUOTA_NOT_ENFORCED')
            measured = dict(root, **{k: val for (k, val) in created.items() if k != 'path'}, filesystem='ext4', filesystem_uuid=plan['mounts']['quota']['uuid'], xflags=attrs[0], accounting=True, enforcement=True, identity_unchanged=True)
            roots.append(measured)
            event('quota-result', measured)
        finally:
            os.close(fd)
    children = {}
    for name in (*a.PHASES, 'management_evidence', 'launcher_output', 'supervisor_output', 'owner_output', 'launcher_declarations', 'supervisor_declarations', 'owner_declarations'):
        parent = dirs['control']['path'] if name == 'launcher_declarations' else dirs['declarations']['path'] if name.endswith('declarations') else dirs['capture']['path']
        children[name] = pin(directory(parent + '/' + name, mode=0o755 if name == 'launcher_declarations' else 0o700))
    observed = copy.deepcopy(v['observed'])
    observed.update(host=plan['host'], ordinary=plan['account'], directories=dirs, parents=parents, roots=roots, installation=installation, capacity_observed={'quota_inventory': before})
    fs = os.statvfs(plan['mounts']['quota']['path'])
    mount = dict(plan['mounts']['quota'], available_bytes=fs.f_bavail * fs.f_frsize, total_bytes=fs.f_blocks * fs.f_frsize, free_inodes=fs.f_favail, total_inodes=fs.f_files)
    q.require(os.stat(mount['path']).st_dev == mount['device'], 'PROVISION_MOUNT_CHANGED')
    observed['mounts'] = {'quota': mount}
    after = quota.inventory(guard)
    newids = {root['project_id'] for root in roots}
    q.require([r for r in after if r['project'] not in newids] == before, 'PROVISION_RETAINED_QUOTA_CHANGED')
    authority = dict(schema='local-hand-q2-preparation-authority/v1', scope=plan['scope'], baseline=plan['baseline'], plan_sha256=hashlib.sha256(driver.encoded(plan)).hexdigest(), preparation_id=plan['preparation_id'], receipt_sha256=hashlib.sha256(driver.encoded(observed)).hexdigest())
    (facts, authority, manifest) = driver.facts_from_observed(plan, observed, children, authority)
    assembled = a.assemble(facts)
    if v.get('transport') == 'mcp':
        assembled['policy']['execution_entrypoint'] = installation['installed']['package_root'] + '/local_hand_mcp/server.py'
    if v.get('cancellation') is True:
        assembled['policy']['principals'][facts['identity']['principal_id']]['scopes'].append('lh:cancel')
    if v.get('scopes'):
        assembled['policy']['principals'][facts['identity']['principal_id']]['scopes'] = v['scopes']
    if v.get('scopes') or v.get('cancellation') is True or v.get('transport') == 'mcp':
        from local_hand_jobs.policy import Policy
        assembled['resident']['request']['expected'] = Policy(assembled['policy']).expected(assembled['resident']['request']['profile_ref'])
        from local_hand_jobs.contract import request_digest
        assembled['resident']['request']['request_digest'] = request_digest(assembled['resident']['request'])
    (uid, gid) = (plan['account']['uid'], plan['account']['gid'])
    policy_path = facts['paths']['policy']
    save(policy_path, assembled['policy'], uid=uid, gid=gid)
    if v.get('transport') == 'mcp':
        save(v['mcp']['auth_config'], v['auth'], uid=uid, gid=gid)
    save(Path(facts['paths']['authority_root']) / 'authority.json', dict(authority_id=facts['identity']['authority_id'], ledger_id=assembled['ledger_id'], state_root=facts['paths']['broker_root']), uid=uid, gid=gid)
    code = "import importlib.util,json,sys; source,policy,ledger,site,tools=sys.argv[1:];sys.path[:0]=[site,tools];s=importlib.util.spec_from_file_location('init_ledger',source);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);print(json.dumps(m.initialize_ledger(json.load(open(policy)),ledger)))"
    argv = [plan['tools']['setpriv']['path'], '--reuid=' + str(uid), '--regid=' + str(gid), '--clear-groups', '--bounding-set=-all', '--inh-caps=-all', '--ambient-caps=-all', '--no-new-privs', '--', installation['installed']['programs']['python']['path'], '-I', '-B', '-c', code, installation['source']['root'] + '/tests/e3_host/q2_prepare_assembly.py', policy_path, assembled['ledger_id'], installation['installed']['package_root'], installation['source']['root'] + '/tools']
    ledger = json.loads(command(argv))
    value = dict(schema='local-hand-task-service/v1', policy=assembled['policy'], policy_path=policy_path, request=assembled['resident']['request'], principal_id=facts['identity']['principal_id'], chain=assembled['chain'], controller_envelope=assembled['launcher']['controller_envelope'], setpriv=facts['setpriv'], python=installation['installed']['programs']['python'], declarations=children['launcher_declarations'], intents=children['launcher_output'], transport=v.get('transport', 'broker'), mcp=v.get('mcp'))
    save(reservation / 'launch-static.json', value)
    save(reservation / 'prepared-formal.json', dict(facts=facts, assembled=assembled, ledger=ledger, children=children))
    save(reservation / 'preparation-result.json', observed)
    return dict(status='PREPARED', launch=value, installation=installation, children=children, reservation=str(reservation))
