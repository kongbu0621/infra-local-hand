"""One fixed current-install verification, carried in memory by the RC2 caller.

This module has no network entry point and never installs or loads a module.
The host pins its exact source and supplies the historical package/mount binding.
"""
import json
import os
import re
import resource
import selectors
import subprocess
import sys
import time


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()+b'\n'


def limits():
    os.umask(0o077)
    for key, value in ((resource.RLIMIT_AS, 256*1048576), (resource.RLIMIT_NOFILE, 128), (resource.RLIMIT_CPU, 120)):
        soft, hard = resource.getrlimit(key)
        require(hard == resource.RLIM_INFINITY or hard >= value, 'GUEST_INHERITED_LIMIT')
        resource.setrlimit(key, (value, hard))


def boot():
    fd = os.open('/proc/sys/kernel/random/boot_id', os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        raw = os.read(fd, 38)
    finally:
        os.close(fd)
    require(len(raw)==37 and raw.endswith(b'\n'), 'GUEST_BOOT')
    value = raw[:-1].decode('ascii')
    require(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value), 'GUEST_BOOT')
    return value


class Budget:
    def __init__(self):
        self.origins = self.previous = self.clocks()
        self.child = None
        self.starttime = None
        self.last = {}

    def clocks(self):
        return [time.clock_gettime_ns(clock) for clock in (time.CLOCK_MONOTONIC, time.CLOCK_BOOTTIME)]

    def check(self):
        now = self.clocks()
        require(all(p <= n < s+120000000000 for p,n,s in zip(self.previous,now,self.origins)), 'GUEST_DEADLINE')
        self.previous = now
        own, children = (resource.getrusage(k) for k in (resource.RUSAGE_SELF, resource.RUSAGE_CHILDREN))
        cpu = own.ru_utime+own.ru_stime+children.ru_utime+children.ru_stime
        rss = (own.ru_maxrss+children.ru_maxrss)*1024
        child = self.child
        if child is not None and child.poll() is None:
            fd = os.open('/proc/'+str(child.pid)+'/stat', os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
            try:
                raw = os.read(fd, 4097)
            finally:
                os.close(fd)
            head,sep,tail = raw.rpartition(b') ');fields = tail.split()
            require(len(raw)<=4096 and sep and head.startswith(str(child.pid).encode()+b' (')
                and len(fields)>=22 and all(fields[i].isdigit() for i in (11,12,19,21)), 'GUEST_CHILD_STAT')
            start = int(fields[19])
            require(start>0 and (self.starttime is None or self.starttime==start), 'GUEST_CHILD_IDENTITY')
            self.starttime = start
            cpu += (int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK')
            rss += int(fields[21])*os.sysconf('SC_PAGE_SIZE')
        require(cpu<=120 and rss<=512*1048576, 'GUEST_USAGE')
        self.last = dict(cpu_nanoseconds=int(cpu*1000000000)+1, rss_peak_bytes=rss,
            elapsed_nanoseconds=max(now[0]-self.origins[0],now[1]-self.origins[1]))
        return dict(self.last)


def commands(package, target):
    require(type(package) is dict and type(package.get('Package')) is str
        and re.fullmatch(r'linux-modules-extra-[0-9][a-zA-Z0-9.+-]*', package['Package']), 'GUEST_PACKAGE')
    require(type(target) is str and target.startswith('/') and os.path.normpath(target)==target
        and re.fullmatch(r'/[A-Za-z0-9_./-]+', target), 'GUEST_TARGET')
    name = package['Package']
    return [('kernel',['uname','-r']), ('installed-package',['dpkg-query','-W','-f=${Status}\t${Version}',name]),
        ('package-integrity',['dpkg','--verify',name]), ('module-vermagic',['modinfo','-F','vermagic','quota_v2']),
        ('module-resolution',['modprobe','--show-depends','quota_v2']),
        ('quota-mount',['findmnt','--json','--mountpoint',target,'-o','UUID,FSTYPE,OPTIONS'])]


def run(argv, budget):
    budget.check()
    child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C','LC_ALL':'C'}, preexec_fn=limits)
    budget.child, budget.starttime = child, None
    output = dict(stdout=bytearray(),stderr=bytearray());eof = dict(stdout=False,stderr=False)
    selector = selectors.DefaultSelector()
    try:
        for name in output:
            stream = getattr(child,name);os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,name)
        while selector.get_map() or child.poll() is None:
            budget.check()
            for key,_ in selector.select(0.025):
                name=key.data;raw=os.read(key.fileobj.fileno(),min(16385-len(output[name]),16384))
                if raw:
                    output[name].extend(raw);require(len(output[name])<=16384,'GUEST_STREAM_BOUND')
                else:
                    eof[name]=True;selector.unregister(key.fileobj)
        budget.check()
        return dict(exit=child.returncode,eof=all(eof.values()),**{k:bytes(v).decode('utf-8','strict') for k,v in output.items()})
    finally:
        selector.close()
        child.stdout.close();child.stderr.close()
        # No retry, reconnect, service signal or attempted recovery on failure.


def verify(description, *, runner=run, boot_reader=boot, budget=None):
    require(type(description) is dict and set(description)=={'nonce','package','quota'},'GUEST_DESCRIPTION')
    require(type(description['nonce']) is str and re.fullmatch(r'[0-9a-f]{64}',description['nonce']), 'GUEST_NONCE')
    budget = Budget() if budget is None else budget
    first = boot_reader();steps=[]
    for label,argv in commands(description['package'],description['quota']['target']):
        result=runner(argv,budget);steps.append(dict(label=label,argv=argv,**result))
        require(type(result['exit']) is int and result['exit']==0 and result['eof'] is True and result['stderr']=='', 'GUEST_COMMAND_FAILED')
    last = boot_reader();require(first==last,'GUEST_BOOT_CHANGED')
    return dict(schema='local-hand-q2-current-guest/v1',status='VERIFIED',nonce=description['nonce'],
        boot_id=first,boot_end=last,steps=steps,package_install_calls=0,module_load_calls=0,reboots=0,
        management_usage=budget.check())


def main():
    limits()
    require(len(sys.argv)==2 and len(sys.argv[1])<=4096,'GUEST_ARGUMENTS')
    value=verify(json.loads(sys.argv[1]));raw=canonical(value)
    require(len(raw)<=65536,'GUEST_REPORT_BOUND')
    sys.stdout.buffer.write(raw);sys.stdout.buffer.flush()


if __name__=='__main__':
    main()
