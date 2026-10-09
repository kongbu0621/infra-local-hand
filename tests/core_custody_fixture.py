"""Portable synthetic records for strict independent custody consumers."""
from e3_host import q2_core_prior_attempt as p
c=p.c

def evidence(implementation,nonce,sources):
    originals=[]
    for i,(name,(size,sha)) in enumerate(p.previous_maintenance_pins().items()):
        originals.append(dict(basename=name,bytes=size,sha256=sha,metadata=dict(dev=1,ino=100+i,
            mode=33152,uid=1000,gid=1000,nlink=1,size=size,blocks=1,mtime_ns=1,ctime_ns=1)))
    return dict(schema='lhq-retained-custody/v1',binding=dict(D=implementation['commit'],nonce=nonce,
        source_sha256=sources['q2_journal_retained_fds.py']['sha256'],
        history_sha256=c.sha256(c.canonical(p.maintenance_resume(),newline=True)),
        set_sha256=c.sha256(c.canonical(originals,newline=True))),pid=321,starttime=1,count=55,
        checks=12,originals=originals,ipc_bytes=8192,cpu_nanoseconds=1000,rss_bytes=1000000,
        state='HELD_UNTIL_TEARDOWN')

def completion(receipt_sha):
    return dict(returncode=0,receipt_sha256=receipt_sha,
        child=dict(returncode=0,cpu_nanoseconds=2000,rss_peak_bytes=1000000),
        usage=dict(cpu_nanoseconds=10000000,rss_peak_bytes=10000000))
