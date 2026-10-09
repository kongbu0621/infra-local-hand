"""One invocation's inherited, bounded custody of already verified originals.

No path reopen, subprocess, remote action, discovery, retry, or replacement child.
Only the Linux coordinator imports this source. Portable validators use summaries.
"""
import hashlib
import json
import os
import resource
import select
import socket
import stat
import time

LIMIT = 128
MAX_CHECKS = 64
IPC_LIMIT = 2 * 1048576
META = ('dev', 'ino', 'mode', 'uid', 'gid', 'nlink', 'size', 'blocks', 'mtime_ns', 'ctime_ns')
ACTIVE = []


def need(ok, reason):
    if not ok:
        error=RuntimeError('GROWTH_CUSTODY_' + reason)
        error.diagnostic=dict(operation='retained_custody',reason=str(error))
        raise error


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii') + b'\n'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def metadata(info):
    return {key: getattr(info, 'st_' + key) for key in META}


def credentials():
    return (os.getuid(), os.geteuid(), os.getgid(), os.getegid(), tuple(os.getgroups()))


def proc(pid, name, limit):
    fd = os.open('/proc/' + str(pid) + '/' + name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        raw = os.read(fd, limit + 1)
        need(len(raw) <= limit and not os.read(fd, 1), 'PROC_BOUND')
        return raw
    finally:
        os.close(fd)


def process_stat(pid):
    raw = proc(pid, 'stat', 4096)
    tail = raw[raw.rindex(b')') + 2:].split()
    need(len(tail) >= 22 and tail[0] not in (b'Z', b'X'), 'PROCESS_DEAD')
    return int(tail[19]), (int(tail[11]) + int(tail[12])) / os.sysconf('SC_CLK_TCK')


class Channel:
    def __init__(self, sock, remaining):
        self.sock, self.remaining, self.total = sock, remaining, 0
        sock.setblocking(False)

    def deadline(self):
        return time.monotonic() + min(5., self.remaining())

    def transfer(self, data, count, end, writing):
        chunks = bytearray()
        offset = 0
        while offset < count:
            remaining = min(end - time.monotonic(), self.remaining())
            need(remaining > 0, 'IPC_TIMEOUT')
            reads, writes, _ = select.select([] if writing else [self.sock],
                [self.sock] if writing else [], [], remaining)
            need(reads or writes, 'IPC_TIMEOUT')
            try:
                part = self.sock.send(data[offset:]) if writing else self.sock.recv(count - offset)
            except BlockingIOError:
                continue
            need(bool(part), 'IPC_EOF')
            size = part if writing else len(part)
            if not writing:
                chunks.extend(part)
            offset += size
            self.total += size
            need(self.total <= IPC_LIMIT, 'IPC_TOTAL')
        return bytes(chunks)

    def send(self, value, limit, end):
        raw = encoded(value)
        need(len(raw) <= limit, 'MESSAGE_BOUND')
        self.transfer(len(raw).to_bytes(4, 'big') + raw, len(raw) + 4, end, True)

    def receive(self, limit, end):
        size = int.from_bytes(self.transfer(None, 4, end, False), 'big')
        need(0 < size <= limit, 'MESSAGE_BOUND')
        raw = self.transfer(None, size, end, False)
        value = json.loads(raw)
        need(encoded(value) == raw, 'MESSAGE_CANONICAL')
        return value


def verify(directory, anchor, rows, creds, after_create, remaining):
    remaining()
    need(credentials() == creds, 'CREDENTIALS')
    current = metadata(os.fstat(directory))
    keys = ('dev', 'ino', 'mode', 'uid', 'gid', 'nlink') if after_create else META
    need(all(current[k] == anchor[k] for k in keys), 'ANCHOR_DRIFT')
    seen = set()
    for name, fd, before, size, digest in rows:
        remaining()
        info = os.fstat(fd)
        now = metadata(info)
        need(now == before == metadata(os.stat(name, dir_fd=directory, follow_symlinks=False)), 'IDENTITY_DRIFT')
        need(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
            and info.st_nlink == 1 and info.st_uid == anchor['uid']
            and info.st_gid == anchor['gid'] and info.st_dev == anchor['dev']
            and 0 <= size <= 65536 and info.st_size == size, 'FILE_PROTECTION')
        key = (info.st_dev, info.st_ino)
        need(key not in seen, 'INODE_ALIAS')
        seen.add(key)
        raw = os.pread(fd, size + 1, 0)
        need(len(raw) == size and sha(raw) == digest, 'FILE_HASH')
        need(metadata(os.fstat(fd)) == before
            == metadata(os.stat(name, dir_fd=directory, follow_symlinks=False)), 'READ_DRIFT')
    remaining()


def child(sock, directory, anchor, rows, creds, binding, remaining):
    # Known inherited descriptor space, not a filesystem or process scan.
    keep = {0, 1, 2, directory, sock.fileno(), *(row[1] for row in rows)}
    start = 3
    for fd in sorted(keep - {0, 1, 2}):
        os.closerange(start, fd)
        start = fd + 1
    need(all(fd < LIMIT for fd in keep), 'INHERITED_FD_BOUND')
    os.closerange(start, 2147483647)
    channel = Channel(sock, remaining)
    sequence = 0
    try:
        ready_end=channel.deadline()
        def bounded(end):
            left=min(end-time.monotonic(),remaining())
            need(left>0,'IPC_TIMEOUT');return left
        verify(directory, anchor, rows, creds, False, lambda:bounded(ready_end))
        channel.send(dict(binding=binding, op='READY', seq=0, count=len(rows)), 16384, ready_end)
        while True:
            # Idle lifetime is bounded by the original window; an individual
            # request/response has at most five seconds once framing starts.
            need(select.select([sock], [], [], remaining())[0], 'WINDOW')
            end=channel.deadline()
            request = channel.receive(4096, end)
            need(type(request) is dict and set(request) == {'binding', 'op', 'seq', 'after_create'}
                and request['binding'] == binding and type(request['seq']) is int
                and request['seq'] == sequence + 1 and type(request['after_create']) is bool, 'REQUEST')
            sequence += 1
            need(request['op'] in ('CHECK', 'RELEASE'), 'OPERATION')
            if request['op'] == 'CHECK':
                need(sequence <= MAX_CHECKS, 'CHECK_LIMIT')
                verify(directory, anchor, rows, creds, request['after_create'], lambda:bounded(end))
            else:
                need(sequence <= MAX_CHECKS + 1, 'CHECK_LIMIT')
                verify(directory, anchor, rows, creds, request['after_create'], lambda:bounded(end))
            channel.send(dict(binding=binding, op=request['op'], seq=sequence, count=len(rows)),
                16384, end)
            if request['op'] == 'RELEASE':
                return 0
    finally:
        sock.close()
        for _, fd, _, _, _ in rows:
            os.close(fd)
        os.close(directory)


class Custodian:
    def __init__(self, anchor, pins, *, commit, nonce, source_sha256, history_sha256):
        self.pidfd = self.pid = self.channel = None
        self.exit = None
        self.sequence = 0
        self.rss_peak = 0
        self.after_create = False
        self.remaining = anchor.deadline.remaining
        self.rows = tuple((name, fd, {k: before[k] for k in META}, *pins[name])
            for name, fd, before in anchor.held if name in pins)
        need(len(self.rows) == len(pins) == 55, 'SET_COUNT')
        need(len({row[1] for row in self.rows}) == len(self.rows), 'FD_ALIAS')
        need(resource.getrlimit(resource.RLIMIT_NOFILE)[0] == LIMIT, 'FD_LIMIT')
        creds = credentials()
        need(creds[0] == creds[1] == anchor.info['uid'] != 0
            and creds[2] == creds[3] == anchor.info['gid'], 'ORDINARY_OWNER')
        self.binding = dict(D=commit, nonce=nonce, source_sha256=source_sha256,
            history_sha256=history_sha256,
            set_sha256=sha(encoded([dict(basename=n, metadata=m, bytes=s, sha256=h)
                for n, _, m, s, h in self.rows])))
        for key, value in self.binding.items():
            need(type(value) is str and len(value) == (40 if key == 'D' else 64)
                and all(ch in '0123456789abcdef' for ch in value), 'BINDING')
        left, right = socket.socketpair()
        try:
            self.pid = os.fork()
            if self.pid == 0:
                code = 3
                try:
                    code = child(right, anchor.fd, anchor.info, self.rows, creds, self.binding, self.remaining)
                except BaseException:
                    pass
                os._exit(code)
            right.close()
            self.channel = Channel(left, self.remaining)
            self.pidfd = os.pidfd_open(self.pid, 0)
            self.starttime, _ = process_stat(self.pid)
            need(not select.select([self.pidfd], [], [], 0)[0], 'EARLY_EXIT')
            self.response('READY', 0)
            self.usage()
            # Only READY + exact process liveness allow surrender of parent copies.
            for _, fd, _, _, _ in self.rows:
                os.close(fd)
            anchor.held[:] = [row for row in anchor.held if row[0] not in pins]
            ACTIVE.append(self)
        except BaseException:
            left.close()
            right.close()
            if self.pid:
                self.reap()
            if self.pidfd is not None:
                os.close(self.pidfd)
            raise

    def response(self, operation, sequence, end=None):
        value = self.channel.receive(16384, self.channel.deadline() if end is None else end)
        need(type(value) is dict and set(value)=={'binding','op','seq','count'}
            and type(value['seq']) is int and type(value['count']) is int
            and value == dict(binding=self.binding, op=operation, seq=sequence, count=55), 'RESPONSE')

    def usage(self):
        need(self.exit is None and not select.select([self.pidfd], [], [], 0)[0], 'EARLY_EXIT')
        start, cpu = process_stat(self.pid)
        need(start == self.starttime, 'PROCESS_IDENTITY')
        status = proc(self.pid, 'status', 16384)
        lines = dict(line.split(b':', 1) for line in status.splitlines() if b':' in line)
        rss = lines[b'VmRSS'].split()
        need(len(rss) == 2 and rss[1] == b'kB' and int(rss[0]) > 0, 'RSS_UNKNOWN')
        self.rss_peak = max(self.rss_peak, int(rss[0]) * 1024)
        return cpu, self.rss_peak

    def check(self, after_create=False):
        self.usage()
        self.sequence += 1
        need(self.sequence <= MAX_CHECKS, 'CHECK_LIMIT')
        self.after_create = self.after_create or after_create
        end=self.channel.deadline()
        self.channel.send(dict(binding=self.binding, op='CHECK', seq=self.sequence,
            after_create=self.after_create), 4096, end)
        self.response('CHECK', self.sequence,end)
        self.usage()

    def summary(self):
        cpu, rss = self.usage()
        return dict(schema='lhq-retained-custody/v1', binding=dict(self.binding),
            pid=self.pid, starttime=self.starttime, count=55, checks=self.sequence,
            originals=[dict(basename=n, metadata=m, bytes=s, sha256=h) for n, _, m, s, h in self.rows],
            ipc_bytes=self.channel.total, cpu_nanoseconds=int(cpu * 1e9), rss_bytes=rss,
            state='HELD_UNTIL_TEARDOWN')

    def reap(self):
        end = time.monotonic() + min(5., self.remaining())
        while self.exit is None:
            pid, status, usage = os.wait4(self.pid, os.WNOHANG)
            if pid:
                self.exit = dict(returncode=os.waitstatus_to_exitcode(status),
                    cpu_nanoseconds=int((usage.ru_utime + usage.ru_stime) * 1e9),
                    rss_peak_bytes=max(self.rss_peak, usage.ru_maxrss * 1024))
                break
            delay = min(.01, self.remaining(), end - time.monotonic())
            need(delay > 0, 'REAP_TIMEOUT')
            time.sleep(delay)
        return self.exit

    def close(self):
        error = None
        try:
            self.sequence += 1
            need(self.sequence <= MAX_CHECKS + 1, 'CHECK_LIMIT')
            end=self.channel.deadline()
            self.channel.send(dict(binding=self.binding, op='RELEASE', seq=self.sequence,
                after_create=self.after_create), 4096, end)
            self.response('RELEASE', self.sequence,end)
        except BaseException as caught:
            error = caught
        finally:
            self.channel.sock.close()
            try:
                result = self.reap()
            finally:
                if self in ACTIVE:
                    ACTIVE.remove(self)
                os.close(self.pidfd)
        if error is not None:
            raise error
        need(result['returncode'] == 0, 'CHILD_EXIT')
        return result
