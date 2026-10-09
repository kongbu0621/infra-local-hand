"""Synthetic old local failure records; never contain or read field evidence."""
import copy
import io
import json
import tarfile
from e3_host import q2_core_prior_attempt as p


def source_projection():
    originals={n:dict(bytes=v[0],sha256=v[1]) for n,v in p.LOCAL_PREFLIGHT_PINS.items()}
    originals.update({n:dict(bytes=100,sha256='b'*64) for n in p.LOCAL_PREFLIGHT_RECORDS})
    return dict(schema='local-hand-q2-local-preflight-source/v1',summary=p.local_preflight_summary(),
        archive=dict(bytes=10240,sha256='a'*64),originals=originals,freeze_sha256='b'*64,
        callers={n:'c'*64 for n in p.LOCAL_PREFLIGHT_CALLERS})


def archive(files):
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w',format=tarfile.USTAR_FORMAT) as target:
        for name,raw in sorted(files.items()):
            item=tarfile.TarInfo(name);item.size=len(raw);item.mode=0o600
            target.addfile(item,io.BytesIO(raw))
    return stream.getvalue()


def records(monkeypatch,*consumers):
    encode=lambda value:(json.dumps(value,sort_keys=True,indent=2)+'\n').encode('ascii')
    summary=dict(D=p.LOCAL_PREFLIGHT_D,phase='preflight',exit_code=3,state='BLOCKED',
        reason='GROWTH_USAGE_UNKNOWN',diagnostic={},marker_created=False,ssh_requests=0,
        errno=None,error_type='ObservationError')
    usage=dict(cpu_nanoseconds=12345,rss_peak_bytes=1048576)
    pre={k:v for k,v in summary.items() if k not in ('D','phase','exit_code')}
    pre.update(management_usage=usage,window_binding=dict(boot_id='1'*36,origins=[1,2]))
    files={'fd2-caller-started.json':encode(dict(D=p.LOCAL_PREFLIGHT_D,session=p.LOCAL_PREFLIGHT_SESSION)),
        'fd2-caller.stderr':b'','fd2-preflight.stderr':b'',
        'fd2-caller.stdout':encode(summary),'fd2-summary.json':encode(summary),
        'fd2-preflight.stdout':encode(pre)}
    pins={n:(len(raw),p.c.sha256(raw)) for n,raw in files.items()}
    for module in (p,*consumers):monkeypatch.setattr(module,'LOCAL_PREFLIGHT_PINS',copy.deepcopy(pins))
    freeze=dict(R=p.c.RULE['commit'],A=p.c.HOST_FD_BASELINE['commit'],C=p.c.HOST_FD_CLOSURE['commit'],
        scope=p.LOCAL_PREFLIGHT_SCOPE,state='FROZEN_FD1_VERIFIED',
        implementation=dict(commit=p.LOCAL_PREFLIGHT_D,tree='a20bf680b8f3d975248a91b251fc7502729b5f46'),
        callers={n:'c'*64 for n in p.LOCAL_PREFLIGHT_CALLERS},
        fd2=dict(session=p.LOCAL_PREFLIGHT_SESSION,state='NOT_STARTED'),
        fd3=dict(session='lhqcore-20261007a',state='NOT_RUN'))
    files['freeze-complete.json']=encode(freeze)
    result=dict(D=p.LOCAL_PREFLIGHT_D,session=p.LOCAL_PREFLIGHT_SESSION,
        freeze_sha256=p.c.sha256(files['freeze-complete.json']),state='PREFLIGHT_FAILED_STOP_AND_RETAIN',
        retained={n:dict(bytes=v[0],sha256=v[1]) for n,v in pins.items()},
        core_package='NOT_BUILT',FD3='NOT_RUN',H01='NOT_RUN',Q4='NOT_RUN',H11='NOT_RUN',
        reason='GROWTH_USAGE_UNKNOWN',diagnostic={},errno=None,error_type='ObservationError',
        maintenance_marker_created=False,maintenance_actions_started=False,
        eleven_historical_generations_still_consumed=True,failed_sample_measurements='NOT_RETAINED',
        process_identity='NOT_IDENTIFIED_BY_RETURN',caller_invocations=1,execute_invocations=0,
        ssh_requests=0,last_valid_management_usage=usage)
    files['execution-result.json']=encode(result)
    files['release-gate.json']=encode(dict(freeze,state='FD2_PREFLIGHT_FAILED_FD3_NOT_RUN',fd2=result))
    raw=archive(files)
    spec=dict(path='/synthetic/old09c-local-retained.tar',bytes=len(raw),sha256=p.c.sha256(raw),
        freeze_sha256=result['freeze_sha256'],callers=freeze['callers'])
    return raw,spec,files
