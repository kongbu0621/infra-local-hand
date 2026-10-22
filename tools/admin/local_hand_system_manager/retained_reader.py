"""Explicit read-only filesystem rebinding for a retained task's original policy.

This compatibility reader composes an independently verified installed runtime.
It does not rewrite policies, requests, leases, events or execution root grants.
The administrator's separate declaration pins the original policy bytes and
evidence directory to one ext4 filesystem and one protected loop backing path.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import re
import selectors
import stat
import subprocess
import time

from local_hand_jobs import cli, manager_binding
from local_hand_jobs.broker import Broker
from local_hand_jobs.bootstrap_roots import validate_root
from local_hand_jobs.contract import JobError, strict_loads
from local_hand_jobs.deployment import verify_release
from local_hand_jobs.evidence import EvidenceStore, _close_descriptors, _open_root
from local_hand_jobs.policy import Policy
from local_hand_jobs.registry import Registry
from local_hand_jobs.resources import AuthorityLock, verify_local_filesystem
from local_hand_jobs.state import StateStore
from local_hand_jobs.task_session import read_descriptor

SCHEMA = 'local-hand-retained-filesystem/v1'
# One exact mount and seven selected fields. A valid near-PATH_MAX target can
# exceed 16 KiB after JSON escaping; retain bounded capture with that headroom.
MOUNT_OUTPUT_LIMIT = 256 * 1024
MOUNT_TIMEOUT = 5


def require(ok, message):
    if not ok:
        raise JobError('CONFLICT', message)


def canonical(path):
    require(type(path) is str and path.startswith('/') and str(Path(path)) == path
            and '..' not in Path(path).parts and path != '/', 'Invalid retained binding path')
    return Path(path)


def validate(binding, policy_path, policy):
    require(type(binding) is dict and set(binding) == {
        'schema', 'policy_path', 'policy_sha256', 'original_root', 'filesystem'},
        'Invalid retained filesystem declaration')
    require(binding['schema'] == SCHEMA and binding['policy_path'] == str(policy_path)
            and type(binding['policy_sha256']) is str
            and re.fullmatch('[0-9a-f]{64}', binding['policy_sha256']) is not None,
            'Retained declaration belongs to another policy')
    root, pin = cli._admitted_evidence_store(policy)
    validate_root(binding['original_root'], expected_uid=os.geteuid())
    require(pin is not None and binding['original_root'] == dict(path=str(root), **pin),
            'Retained declaration differs from the original admission')
    filesystem = binding['filesystem']
    require(type(filesystem) is dict and set(filesystem) == {'mountpoint', 'uuid', 'backing_file'},
            'Invalid retained filesystem identity')
    mountpoint = canonical(filesystem['mountpoint'])
    canonical(filesystem['backing_file'])
    require(mountpoint in root.parents and type(filesystem['uuid']) is str
            and re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', filesystem['uuid']) is not None,
            'Retained directory is outside the declared filesystem')
    return root, pin


def protected_backing_parent(path):
    """The service need not read the private image; nobody ordinary may replace it."""
    parent = canonical(path).parent
    # Opening a 0700 root-owned parent O_RDONLY is intentionally impossible for
    # the reader. O_PATH permits metadata checks, never directory enumeration.
    fd = os.open('/', os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    failure = None
    try:
        for part in parent.parts[1:]:
            child = os.open(part, os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            previous, fd = fd, child
            _close_descriptors(previous)
            info = os.fstat(fd)
            require(info.st_uid == 0 and not info.st_mode & 0o022,
                    'Backing image ancestry is not administrator protected')
    except BaseException as error:
        failure = error
        raise
    finally:
        _close_descriptors(fd, failure=failure)


def small_read(path):
    with open(path, 'rb') as stream:
        data = stream.read(4097)
    require(len(data) <= 4096, 'Filesystem identity metadata exceeds its bound')
    return data.decode('utf-8').strip()


def mount_output(mountpoint):
    """Bound this fixed read-only client's bytes while capturing, then reap it."""
    process = selector = failure = None
    captured = bytearray()
    try:
        selector = selectors.DefaultSelector()
        process = subprocess.Popen(['/usr/bin/findmnt', '--json', '-M', mountpoint,
            '-o', 'SOURCE,TARGET,FSTYPE,OPTIONS,UUID,MAJ:MIN'],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        os.set_blocking(process.stdout.fileno(), False)
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + MOUNT_TIMEOUT
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise JobError('IO_UNCERTAIN', 'Retained filesystem observation timed out')
            for key, _ in selector.select(min(remaining, 0.05)):
                block = os.read(key.fd, min(4096, MOUNT_OUTPUT_LIMIT + 1 - len(captured)))
                if not block:
                    selector.unregister(key.fileobj)
                    continue
                captured.extend(block)
                if len(captured) > MOUNT_OUTPUT_LIMIT:
                    raise JobError('LIMIT_EXCEEDED', 'Retained filesystem observation exceeds byte limit')
        result = process.wait(timeout=max(0, deadline - time.monotonic()))
        require(result == 0, 'Retained filesystem could not be observed')
        return bytes(captured)
    except (OSError, subprocess.TimeoutExpired) as error:
        failure = JobError('IO_UNCERTAIN', 'Retained filesystem observation did not complete')
        raise failure from error
    except BaseException as error:
        failure = error
        raise
    finally:
        cleanup_error = None

        def cleanup(action):
            nonlocal cleanup_error
            try:
                action()
            except BaseException as error:
                if cleanup_error is None:
                    cleanup_error = error

        if process is not None:
            cleanup(lambda: process.kill() if process.poll() is None else None)
            cleanup(lambda: process.wait(timeout=1))
            if process.stdout is not None:
                cleanup(process.stdout.close)
        if selector is not None:
            cleanup(selector.close)
        if cleanup_error is not None:
            if failure is not None:
                failure.add_note('Retained filesystem observation cleanup also failed')
            else:
                raise JobError('IO_UNCERTAIN', 'Retained filesystem observation cleanup incomplete') from cleanup_error


def observe_filesystem(filesystem, device):
    protected_backing_parent(filesystem['backing_file'])
    value = strict_loads(mount_output(filesystem['mountpoint']))
    require(type(value) is dict and type(value.get('filesystems')) is list
            and len(value['filesystems']) == 1, 'Ambiguous retained filesystem mount')
    row = value['filesystems'][0]
    major_minor = f'{os.major(device)}:{os.minor(device)}'
    require(type(row) is dict and row.get('target') == filesystem['mountpoint']
            and row.get('fstype') == 'ext4' and row.get('uuid') == filesystem['uuid']
            and row.get('maj:min') == major_minor
            and type(row.get('source')) is str and re.fullmatch('/dev/loop[0-9]+', row['source']) is not None
            and type(row.get('options')) is str
            and {'nosuid', 'nodev', 'noexec'} <= set(row['options'].split(',')),
            'Retained filesystem identity or mount protection changed')
    loop = Path('/sys/dev/block') / major_minor / 'loop'
    require(small_read(loop / 'backing_file') == filesystem['backing_file']
            and small_read(loop / 'offset') == '0' and small_read(loop / 'sizelimit') == '0',
            'Retained filesystem uses another backing image or range')
    return (device, row['uuid'], row['target'], filesystem['backing_file'])


def current_pin(root, old, filesystem):
    with _open_root(root, old['uid'], create=False) as descriptor:
        info = os.fstat(descriptor)
        require(info.st_ino == old['inode'] and info.st_uid == old['uid'],
                'Retained directory inode or owner changed')
        observe_filesystem(filesystem, info.st_dev)
        # Check the named mount as well as the held directory; a mount switch
        # must not make a stale descriptor authorize the newly named root.
        named = os.stat(root, follow_symlinks=False)
        require((named.st_dev, named.st_ino, named.st_uid) == (info.st_dev, info.st_ino, info.st_uid),
                'Retained directory changed during observation')
        return dict(device=info.st_dev, inode=info.st_ino, uid=info.st_uid)


class RetainedEvidenceStore(EvidenceStore):
    def __init__(self, root, *, original_identity, filesystem, **kwargs):
        self.original_identity, self.filesystem = original_identity, filesystem
        pin = current_pin(root, original_identity, filesystem)
        super().__init__(root, root_identity=pin, **kwargs)

    @contextmanager
    def _open_store(self, seal_id=None):
        require(current_pin(self.root, self.original_identity, self.filesystem) == self.root_identity,
                'Retained mount changed; reopen the read-only reader')
        with super()._open_store(seal_id) as descriptor:
            yield descriptor
        require(current_pin(self.root, self.original_identity, self.filesystem) == self.root_identity,
                'Retained mount changed during evidence access')

    def _record(self, seal_id):
        # The original DB-authenticated seal also pins st_dev for its zip and
        # manifest. Rebind only that field in this temporary decoded view. The
        # base reader still checks inode, mode, links, owner, size and timestamps
        # against the actual file. Original seal bytes and hashes stay intact.
        record = super()._record(seal_id)
        identities = record.get('artifact_identities')
        require(type(identities) is dict and set(identities) == {'zip', 'manifest'},
                'Retained seal has no complete artifact identities')
        rebound = {}
        for role, identity in identities.items():
            require(type(identity) is list and len(identity) == 8
                    and all(type(value) is int and value >= 0 for value in identity)
                    and identity[0] == self.original_identity['device'],
                    'Retained artifact differs from the original filesystem admission')
            rebound[role] = [self.root_identity['device'], *identity[1:]]
        record['artifact_identities'] = rebound
        return record

    def seal(self, operation_id):
        raise JobError('UNSUPPORTED', 'Retained filesystem binding is read-only')

    def publish_only(self, snapshot):
        raise JobError('UNSUPPORTED', 'Retained filesystem binding is read-only')


def open_reader(policy_path, binding_path):
    """Open the original ledger read-only using one root-owned recovery binding.

    The installed execution runtime is verified separately; this maintenance
    module is not represented as part of that runtime's original release.
    """
    policy_path = str(canonical(str(policy_path)))
    binding = read_descriptor(str(binding_path))
    require(type(binding) is dict and type(binding.get('policy_sha256')) is str
            and re.fullmatch('[0-9a-f]{64}', binding['policy_sha256']) is not None,
            'Missing original policy byte identity')
    policy = Policy.from_file(policy_path, expected_sha256=binding['policy_sha256'])
    root, old = validate(binding, policy_path, policy)
    verify_release(expected_source_commit=policy.source_commit,
                   expected_payload_digest=policy.installed_payload_digest,
                   expected_entrypoint=policy.execution_entrypoint,
                   actual_entrypoint=cli.__file__)
    manager_binding.from_configuration(policy.config.get('process_manager', {}), authority_id=policy.authority_id)
    current_pin(root, old, binding['filesystem'])
    verify_local_filesystem(policy.broker_root)
    verify_local_filesystem(policy.authority_root)
    anchor = Path(policy.authority_root) / 'authority.json'
    descriptor = os.open(anchor, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    failure = None
    try:
        info = os.fstat(descriptor)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 8192,
                'Invalid retained authority anchor')
        registration = strict_loads(os.read(descriptor, 8193))
        require(type(registration) is dict and type(registration.get('ledger_id')) is str,
                'Missing retained ledger identity')
    except BaseException as error:
        failure = error
        raise
    finally:
        _close_descriptors(descriptor, failure=failure)
    authority = AuthorityLock(anchor, authority_id=policy.authority_id,
                              ledger_id=registration['ledger_id'], state_root=policy.broker_root)
    state = broker = None
    try:
        state = StateStore(Path(policy.broker_root) / 'jobs.sqlite', policy.authority_id,
                           registration['ledger_id'], read_only=True)
        broker = Broker(state, policy, Registry(), None, quota_required=True)

        def no_publish(_):
            raise JobError('UNSUPPORTED', 'Retained filesystem binding is read-only')

        def authorize(principal, operation_id):
            with state.transaction() as tx:
                broker._row(tx, 'job', operation_id, principal, 'lh:evidence')

        broker.evidence = RetainedEvidenceStore(root, original_identity=old,
            filesystem=binding['filesystem'], snapshot_provider=no_publish,
            register_seal=no_publish, is_registered=broker.is_registered,
            list_seals=broker.list_seals, authorize=authorize,
            max_source_bytes=policy.limits['retained_bytes'],
            max_artifact_bytes=policy.limits['retained_bytes'])
        broker.authority_lock = authority
        return broker
    except BaseException as failure:
        for resource in (broker, state, authority):
            if resource is not None:
                try:
                    resource.close()
                except BaseException:
                    failure.add_note('Retained reader cleanup also failed')
        raise
