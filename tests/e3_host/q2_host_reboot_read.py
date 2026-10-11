"""HB1/HB2 fixed local read. No product entry point or VM/SSH operation.

The private caller freezes the source-derived request and authority. Test roots,
clock and process seams are Python-only; none can be selected by field arguments.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import selectors
import stat
import subprocess
import time
import traceback
import uuid

R = '10d2a5c827964989f41ca6e8eeac3d44de6d0f04'
A = 'b2a326036b634bb007a6adeec8929084bce3ccbd'
C = '62d485c499d02744fbf83a8653c1aa7f80be0584'
SCOPE = 'LH-Q2-CORE-HOST-REBOOT-READ-v1'
EVENT = 'LH-Q2-CORE-HOST-REBOOT-READ-20261011-01'
SESSION = 'lhqhost-20261011a'
B = 'e2858815c3d1d340a69bf2c0d69d37becfd48bb1ce523fd0254cf62fc83861a8'
LIMITS = dict(cpu_seconds=240, wall_seconds=240, aggregate_rss_bytes=1073741824,
              process_as_bytes=536870912, process_fds=256, stream_bytes=65536,
              record_bytes=131072, capture_bytes=2097152, control_children=1,
              control_commands=1)
COSTS = dict(maintenance_obligations=18, old_mib=25283, old_inodes=7364,
             source_preparation_mib=2, source_preparation_inodes=64,
             read_capture_mib=2, read_capture_inodes=64, total_mib=25287,
             total_inodes=7492)
PARTITIONS = dict(parent_cpu=30, reader_cpu=180, control_cpu=30,
                  parent_as=268435456, reader_as=536870912, control_as=268435456)
ROLES = {'system', 'original_system', 'quota', 'journal', 'evidence', 'seed'}
ARGV = ['/usr/bin/ss', '-H', '-4', '-ltn', 'sport = :22221']
META = ('dev', 'ino', 'mode', 'uid', 'gid', 'nlink', 'size', 'blocks', 'mtime_ns', 'ctime_ns')
IDENTITY = ('dev', 'ino', 'mode', 'uid', 'gid')


class ReadError(RuntimeError):
    pass


def require(ok, code):
    if not ok:
        raise ReadError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode() + b'\n'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pin(raw):
    return dict(bytes=len(raw), sha256=sha(raw))


def metadata(info):
    return {k: getattr(info, 'st_' + k) for k in META}


def identity(meta):
    return {k: meta[k] for k in IDENTITY}


def parse(raw):
    def unique(items):
        value = {}
        for key, item in items:
            require(key not in value, 'DUPLICATE_KEY')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: require(False, 'JSON_CONSTANT'))


def validate_request(request):
    require(request['R'] == R and request['A'] == A and request['C'] == C and
            request['B'] == B and re.fullmatch('[0-9a-f]{40}', request['D']) and
            request['scope'] == SCOPE and request['event'] == EVENT and
            request['session'] == SESSION, 'AUTHORITY')
    require(request['limits'] == LIMITS and request['costs'] == COSTS, 'LIMITS_OR_COSTS')
    require(str(uuid.UUID(request['nonce'])) == request['nonce'], 'NONCE')
    target = request['target']
    require(target['listener_argv'] == ARGV and
            target['qemu_metadata_path'] == '/usr/bin/qemu-system-x86_64' and
            target['host_boot_path'] == '/proc/sys/kernel/random/boot_id' and
            target['self_namespaces'] == ['/proc/self/ns/' + n for n in ('pid', 'mnt', 'net')]
            and target['maximum_pid_slots'] == 2 and target['ssh_calls'] == 0 and
            target['network_requests'] == 0 and target['foreign_process_cmdline_read'] is False,
            'TARGET_SCOPE')
    require(set(target['images']) == ROLES and
            type(target['old_vm']['pid']) is int and 1 < target['old_vm']['pid'] <= 2147483647,
            'FIXED_OBJECTS')
    require(1 <= len(request['inputs']) <= 48, 'INPUT_COUNT')
    paths = [v['path'] for v in request['inputs'].values()]
    require(len(paths) == len(set(paths)), 'INPUT_ALIAS')
    require(sum(v['bytes'] for v in request['inputs'].values()) <= 4 * 1048576 and
            all(0 <= v['bytes'] <= 1048576 and re.fullmatch('[0-9a-f]{64}', v['sha256'])
                for v in request['inputs'].values()), 'INPUT_BOUNDS')
    require(len(canonical(request)) <= LIMITS['record_bytes'], 'REQUEST_SIZE')


class Budget:
    def __init__(self):
        import resource
        self.resource = resource
        self.began = time.monotonic()
        self.boot_began = time.clock_gettime(time.CLOCK_BOOTTIME)
        self.last = None

    def check(self):
        r = self.resource
        own, child = r.getrusage(r.RUSAGE_SELF), r.getrusage(r.RUSAGE_CHILDREN)
        elapsed = max(time.monotonic() - self.began,
                      time.clock_gettime(time.CLOCK_BOOTTIME) - self.boot_began)
        self.last = dict(cpu_seconds=own.ru_utime + own.ru_stime + child.ru_utime + child.ru_stime,
                         peak_rss_bytes=(own.ru_maxrss + child.ru_maxrss) * 1024,
                         elapsed_seconds=elapsed)
        require(0 <= elapsed < 240 and self.last['cpu_seconds'] < 240 and
                self.last['peak_rss_bytes'] <= 1073741824, 'RESOURCE_LIMIT')
        return self.last

    def configure(self):
        r = self.resource
        for key, cap in ((r.RLIMIT_CPU, PARTITIONS['reader_cpu']), (r.RLIMIT_AS, 536870912),
                         (r.RLIMIT_NOFILE, 256), (r.RLIMIT_CORE, 0),
                         (r.RLIMIT_FSIZE, 2097152)):
            old = r.getrlimit(key)
            require(old[1] == r.RLIM_INFINITY or old[1] >= cap, 'INHERITED_LIMIT')
            r.setrlimit(key, (cap, cap))
            require(r.getrlimit(key) == (cap, cap), 'SET_LIMIT')
        self.check()


class Held:
    """Protected no-follow traversal; no directory enumeration or image content."""
    def __init__(self, check, *, root='/', owner=None, tool_owner=0):
        self.check, self.root, self.tool_owner = check, root, tool_owner
        self.owner = os.geteuid() if owner is None else owner
        self.dirs, self.files, self.absent = {}, {}, []
        fd = os.open(root, os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        self.dirs['/'] = (fd, metadata(os.fstat(fd)), None, None)
        self.qualify(os.fstat(fd), directory=True)

    def qualify(self, info, *, directory=False, executable=False):
        require(info.st_uid in ((self.tool_owner,) if executable else (0, self.owner)) and
                not info.st_mode & 0o022, 'PROTECTION')
        require(stat.S_ISDIR(info.st_mode) if directory else
                stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'TYPE')
        if executable:
            require(info.st_mode & 0o111, 'EXECUTABLE')

    def directory(self, path):
        require(path.startswith('/') and str(PurePosixPath(path)) == path and
                '..' not in PurePosixPath(path).parts, 'PATH')
        current = '/'
        for part in PurePosixPath(path).parts[1:]:
            following = current.rstrip('/') + '/' + part
            if following not in self.dirs:
                self.check()
                parent = self.dirs[current][0]
                fd = os.open(part, os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                             dir_fd=parent)
                self.dirs[following] = (fd, metadata(os.fstat(fd)), parent, part)
                self.qualify(os.fstat(fd), directory=True)
            current = following
        return self.dirs[current][0]

    def open(self, path, *, optional=False, read=False, executable=False):
        self.check()
        require(path not in self.files, 'DUPLICATE_HELD_PATH')
        p = PurePosixPath(path)
        parent = self.directory(str(p.parent))
        flags = os.O_NOFOLLOW | os.O_CLOEXEC
        flags |= (os.O_RDONLY | os.O_NOATIME | os.O_NONBLOCK) if read else os.O_PATH
        try:
            fd = os.open(p.name, flags, dir_fd=parent)
        except FileNotFoundError:
            require(optional, 'MISSING')
            self.absent.append((parent, p.name))
            return None
        before = metadata(os.fstat(fd))
        self.files[path] = (fd, before, parent, p.name)
        self.qualify(os.fstat(fd), executable=executable)
        require(before == metadata(os.stat(p.name, dir_fd=parent, follow_symlinks=False)), 'OPEN_DRIFT')
        return fd, before

    def read(self, path, cap, *, optional=False):
        item = self.open(path, read=True, optional=optional)
        if item is None:
            return None
        fd, before = item
        require(0 <= before['size'] <= cap, 'FILE_LIMIT')
        raw = bytearray()
        while True:
            self.check()
            chunk = os.read(fd, min(65536, cap + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
            require(len(raw) <= cap, 'FILE_LIMIT')
        require(len(raw) == before['size'] and metadata(os.fstat(fd)) == before, 'READ_DRIFT')
        return bytes(raw)

    def recheck(self):
        for fd, before, parent, name in self.dirs.values():
            self.check()
            named = os.stat(self.root, follow_symlinks=False) if parent is None else os.stat(
                name, dir_fd=parent, follow_symlinks=False)
            require(identity(metadata(os.fstat(fd))) == identity(before) == identity(metadata(named)),
                    'DIRECTORY_DRIFT')
        for fd, before, parent, name in self.files.values():
            self.check()
            require(metadata(os.fstat(fd)) == before ==
                    metadata(os.stat(name, dir_fd=parent, follow_symlinks=False)), 'HELD_DRIFT')
        for parent, name in self.absent:
            self.check()
            try:
                os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise ReadError('ABSENCE_DRIFT')

    def close(self):
        for fd, *_ in list(self.files.values()) + list(reversed(self.dirs.values())):
            os.close(fd)
        self.files.clear()
        self.dirs.clear()


class Outputs:
    def __init__(self, held, path):
        self.fd = held.directory(path)
        self.records = {}
        self.allocated = 0

    def save(self, name, value):
        raw = value if type(value) is bytes else canonical(value)
        require(re.fullmatch(r'[a-z0-9-]+(?:\.[a-z]+)+', name) and name not in self.records,
                'OUTPUT_NAME')
        require(len(raw) <= (65536 if name.endswith(('.stdout', '.stderr')) else 131072)
                and len(self.records) < 32 and
                sum(v['bytes'] for v in self.records.values()) + len(raw) <= 2097152,
                'OUTPUT_LIMIT')
        fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=self.fd)
        try:
            offset = 0
            while offset < len(raw):
                count = os.write(fd, raw[offset:offset + 65536])
                require(count > 0, 'OUTPUT_WRITE')
                offset += count
            os.fsync(fd)
            info = os.fstat(fd)
            require(info.st_size == len(raw) and info.st_nlink == 1 and
                    stat.S_IMODE(info.st_mode) == 0o600 and
                    metadata(info) == metadata(os.stat(name, dir_fd=self.fd, follow_symlinks=False))
                    and os.pread(fd, len(raw) + 1, 0) == raw, 'OUTPUT_DRIFT')
            self.allocated += info.st_blocks * 512
            require(self.allocated <= 2097152, 'OUTPUT_ALLOCATION')
            self.records[name] = pin(raw)
        finally:
            os.close(fd)


def kernel(path, cap, *, directory=None):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
    try:
        raw = os.read(fd, cap + 1)
        require(len(raw) <= cap, 'KERNEL_LIMIT')
        return raw
    finally:
        os.close(fd)


def host_identity(target):
    raw = kernel(target['host_boot_path'], 64).decode('ascii').strip()
    require(str(uuid.UUID(raw)) == raw, 'BOOT_FORMAT')
    return dict(boot_id=raw, namespaces={p.rsplit('/', 1)[1]: os.readlink(p)
                                       for p in target['self_namespaces']})


def starttime(raw, pid):
    require(raw.startswith(str(pid).encode() + b' ('), 'STAT_PID')
    tail = raw.rpartition(b') ')[2].split()
    require(len(tail) >= 20 and tail[19].isdigit(), 'STAT_FORMAT')
    return int(tail[19])


def process_identity(pid, qemu, check, *, proc='/proc'):
    check()
    path = proc + '/' + str(pid)
    try:
        fd = os.open(path, os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        return dict(pid=pid, state='ABSENT')
    try:
        first = kernel('stat', 16384, directory=fd)
        beginning = starttime(first, pid)
        exe = os.readlink('exe', dir_fd=fd)
        exestat = metadata(os.stat('exe', dir_fd=fd))
        result = dict(pid=pid, starttime=beginning, exe=exe, exe_metadata=exestat,
                      state='OTHER_EXECUTABLE', stat_sha256=sha(first))
        if exe == '/usr/bin/qemu-system-x86_64' and exestat == qemu:
            cmdline = kernel('cmdline', 65536, directory=fd)
            require(cmdline.endswith(b'\0') and b'\0' in cmdline, 'CMDLINE_FORMAT')
            result.update(state='QEMU', argv_sha256=sha(cmdline),
                          namespaces={n: os.readlink('ns/' + n, dir_fd=fd) for n in ('pid', 'mnt', 'net')})
        check()
        require(beginning == starttime(kernel('stat', 16384, directory=fd), pid) and
                metadata(os.stat('exe', dir_fd=fd)) == exestat and
                os.readlink('exe', dir_fd=fd) == exe and
                (os.fstat(fd).st_dev, os.fstat(fd).st_ino) ==
                (os.stat(path, follow_symlinks=False).st_dev, os.stat(path, follow_symlinks=False).st_ino),
                'PROCESS_DRIFT')
        return result
    finally:
        os.close(fd)


def control_limits():
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_AS, (268435456, 268435456))


def capture(argv, executable, pass_fds, check, save, *, popen=subprocess.Popen):
    """One bounded local child, with real dual EOF and actual completion."""
    record = dict(argv=argv, returncode=None, eof=dict(stdout=False, stderr=False), started=False)
    streams = dict(stdout=bytearray(), stderr=bytearray())
    child = None
    selector = selectors.DefaultSelector()
    try:
        check()
        child = popen(argv, executable=executable, pass_fds=pass_fds, stdin=subprocess.DEVNULL,
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                      env={'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C'}, start_new_session=True,
                      preexec_fn=control_limits)
        record['started'] = True
        for name in streams:
            handle = getattr(child, name)
            os.set_blocking(handle.fileno(), False)
            selector.register(handle, selectors.EVENT_READ, name)
        while selector.get_map() or child.poll() is None:
            check()
            for key, _ in selector.select(0.02):
                raw = os.read(key.fileobj.fileno(), min(65536, 65537 - len(streams[key.data])))
                if not raw:
                    record['eof'][key.data] = True
                    selector.unregister(key.fileobj)
                else:
                    require(len(streams[key.data]) + len(raw) <= 65536, 'STREAM_LIMIT')
                    streams[key.data].extend(raw)
        record['returncode'] = child.wait(timeout=0)
        check()
    except BaseException as error:
        record['error'] = dict(type=type(error).__name__, reason=str(error)[:1024])
        # Only our local control child can be signalled, never an observed PID/VM.
        if child is not None and child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        if child is not None:
            record['returncode'] = child.returncode
    finally:
        selector.close()
        for name, raw in streams.items():
            save('listener.' + name, bytes(raw))
            record[name] = pin(bytes(raw))
            if child is not None:
                getattr(child, name).close()
        save('listener-completion.json', record)
    require(record['started'] and record['returncode'] == 0 and
            all(record['eof'].values()) and 'error' not in record, 'CONTROL_INCOMPLETE')
    require(not streams['stderr'], 'CONTROL_STDERR')
    return bytes(streams['stdout']), record


def listener_state(raw):
    rows = [line.split() for line in raw.splitlines() if line.strip()]
    require(all(len(row) == 5 and row[0] == b'LISTEN' and
                row[1].isdigit() and row[2].isdigit() and
                row[3].rsplit(b':', 1)[-1] == b'22221' for row in rows), 'LISTENER_FORMAT')
    return 'PRESENT' if rows else 'ABSENT'


def observe(request, held, output, check, *, host=host_identity, process=process_identity,
            command=capture):
    target = request['target']
    result = dict(stage='HOST_BEFORE', inputs={}, images={}, processes=[], ssh_calls=0,
                  network_requests=0, vm_actions=0, listener_queries=0)
    try:
        result['host_before'] = host(target)
        result['stage'] = 'INPUTS'
        for role, expected in request['inputs'].items():
            raw = held.read(expected['path'], expected['bytes'])
            require(pin(raw) == {k: expected[k] for k in ('bytes', 'sha256')}, 'SOURCE_PIN')
            result['inputs'][role] = pin(raw)
        result['stage'] = 'TOOLS'
        qemu = held.open(target['qemu_metadata_path'], executable=True)
        ss = held.open(ARGV[0], executable=True)
        result['tools'] = dict(qemu=qemu[1], listener=ss[1])
        require(qemu[1] == request['tool_metadata']['qemu'] and
                ss[1] == request['tool_metadata']['listener'], 'TOOL_IDENTITY')
        result['stage'] = 'FIXED_FILES'
        pidraw = held.read(target['pidfile'], 64, optional=True)
        if pidraw is None:
            result['pidfile'] = dict(state='ABSENT')
            pid = None
        else:
            output.save('pidfile.raw', pidraw)
            require(re.fullmatch(rb'[1-9][0-9]{0,9}\n?', pidraw) is not None and
                    1 < int(pidraw) <= 2147483647, 'PIDFILE_FORMAT')
            pid = int(pidraw)
            result['pidfile'] = dict(state='PRESENT', pid=pid, **pin(pidraw))
        serial = held.open(target['serial_metadata_only'], optional=True)
        result['serial'] = dict(state='ABSENT') if serial is None else dict(state='PRESENT', metadata=serial[1])
        for role, item in sorted(target['images'].items()):
            current = held.open(item['path'])[1]
            require(current['uid'] == held.owner, 'IMAGE_OWNER')
            result['images'][role] = dict(metadata=current,
                matches_retained=(current['dev'], current['ino']) == (item['device'], item['inode']))
        result['stage'] = 'PROCESSES'
        pids = list(dict.fromkeys([target['old_vm']['pid']] + ([] if pid is None else [pid])))
        for number in pids:
            result['processes'].append(process(number, qemu[1], check))
        result['stage'] = 'LISTENER'
        held.recheck()
        result['listener_queries'] = 1
        raw, receipt = command(ARGV, '/proc/self/fd/' + str(ss[0]), (ss[0],), check, output.save)
        result['listener'] = dict(state=listener_state(raw), completion=receipt)
        result['stage'] = 'FINAL'
        final = [process(number, qemu[1], check) for number in pids]
        # /proc stat CPU counters may change; compare semantic identity, not raw digest.
        project = lambda items: [{k: v for k, v in p.items() if k != 'stat_sha256'} for p in items]
        result['processes_after'] = final
        require(project(final) == project(result['processes']), 'PROCESS_FINAL_DRIFT')
        held.recheck()
        result['host_after'] = host(target)
        require(result['host_after'] == result['host_before'], 'HOST_DRIFT')
        result['stage'] = 'COMPLETE'
        result['state'] = 'FIXED_HOST_READ_COMPLETE'
    except BaseException as error:
        result.update(state='INCOMPLETE', error=dict(type=type(error).__name__,
                      errno=getattr(error, 'errno', None), reason=str(error)[:2048],
                      traceback=traceback.format_exc()[-8192:]))
    result['held_files'] = {p: before for p, (_, before, _, _) in held.files.items()}
    result['held_directories'] = len(held.dirs)
    return result


def run_once(request, *, held, output, budget, host=host_identity,
             process=process_identity, command=capture):
    """Caller must create its separate O_EXCL invocation before this entry."""
    binding = dict(event=EVENT, session=SESSION, nonce=request['nonce'], request=pin(canonical(request)))
    output.save('read-started.json', binding)  # duplicate blocks all observations
    try:
        validate_request(request)
        budget.check()
        result = observe(request, held, output, budget.check, host=host, process=process, command=command)
        budget.check()
    except BaseException as error:
        result = dict(state='INCOMPLETE', stage='ADMISSION_OR_BUDGET',
                      error=dict(type=type(error).__name__, reason=str(error)[:2048]))
    result.update(binding, limits=LIMITS, partitions=PARTITIONS, costs=COSTS, usage=budget.last)
    output.save('read-result.json', result)
    output.save('read-index.json', dict(binding=binding, files=dict(output.records),
                                      allocated_bytes=output.allocated, state=result['state']))
    return 0 if result['state'] == 'FIXED_HOST_READ_COMPLETE' else 3
