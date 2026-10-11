"""Consume actual continuation returns without replaying completed mutations.

The original failed receipt and original event prefix remain bound in the final
receipt. The original core package/source selection is independent of the host
repair and the explicitly recorded post-phase source revision.
"""
import copy
import json
import base64
import zlib

from . import q2_core_prior_attempt as p, q2_journal_growth as h, q2_journal_growth_guest as g


def build(raw, marker, receipt, *, implementation, sources, frozen, priors, local_source, failed_source):
    require = lambda ok, reason: p.require(ok, 'CONTINUATION_'+reason)
    pin = lambda b: dict(bytes=len(b),sha256=h.digest(b))
    old = receipt['previous_receipt']; manifest = marker['manifest']
    completed = receipt['post_result']; start = receipt['post_started']
    completion = frozen['coordinator_completion']
    require(receipt['state']=='VERIFIED_AFTER_CONTINUATION' and receipt['returncode']==0,
            'COMPLETION')
    require(old['state']=='STOP_AND_RETAIN' and old['reason']=='GROWTH_PROCESS_ARGV'
        and old['ssh_requests']==1 and old['marker_created'] is True
        and old['started']==sorted(h.STATES[1:7]), 'PREFIX_STATE')
    require(old['D']==marker['D']==manifest['D']==implementation['commit']
        and old['nonce']==marker['nonce']==manifest['nonce']==completed['nonce']==start['nonce']
        and old['manifest_sha256']==marker['manifest_sha256']==h.digest(h.canonical(manifest)), 'BINDING')
    previous = receipt['previous_coordinator_completion']
    require(previous['returncode']==3 and previous['child']['returncode']==0
        and previous['receipt_sha256']==h.digest(h.canonical(old)), 'PREVIOUS_COMPLETION')
    require(manifest['sources']=={n:pin(b) for n,b in sources.items()}, 'ORIGINAL_SOURCES')
    require(manifest['R']==h.R and manifest['A']==h.GR_A and manifest['C']==h.GR_C,
            'AUTHORITY')
    require(p.decode_manifest_inputs(manifest,frozen['persistent_predecessor'])==frozen['source_binding'],
            'INPUTS')
    require(start['original_failure_sha256']==h.digest(h.canonical(old))
        and start['original_events_sha256']==h.digest(raw['events.jsonl']), 'RETAINED_FAILURE')
    events = [json.loads(line) for line in raw['events.jsonl'].splitlines()]
    returns = [row for row in events if row.get('state')=='RETURNED']
    require([row['step'] for row in returns]==list(h.STATES[1:6])
        and events[-1]==dict(state='STARTED',step='BOOTED'), 'PREFIX_ORDER')
    expected = []
    for step in h.STATES[1:7]:
        expected.append((step,'STARTED'))
        if step=='POWERED_OFF':expected.append(('POWER_OFF_TOKEN','STARTED'))
        if step!='BOOTED':expected.append((step,'RETURNED'))
    require([(row['step'],row['state']) for row in events if 'step' in row]==expected,'EFFECT_ORDER')
    results = {row['step']:row['result'] for row in returns}
    require(results['CONSUMED']==dict(manifest_sha256=marker['manifest_sha256']), 'CONSUMED')
    pre_lines = raw['pre.stdout'].splitlines(keepends=True)
    require(len(pre_lines)==2 and raw['pre.stderr']==raw['post.stderr']==b'', 'STREAMS')
    pre,ack = map(json.loads,pre_lines); post = json.loads(raw['post.stdout'])
    require(results['GUEST_QUIET']==pre, 'PRE_RETURN')
    desc = marker['pre_description']; g.descriptor(h.canonical(desc));g.validate_pre_report(pre,desc)
    post_desc = dict(desc,phase='post',pre_report=pre,pre_report_sha256=h.digest(h.canonical(pre)),
        window_seconds=start['window_seconds'],change_seconds=start['change_seconds'])
    g.descriptor(h.canonical(post_desc));g.validate_post_report(post,post_desc)
    require(start['description_sha256']==h.digest(h.canonical(post_desc))
        and completed['source_binding_sha256']==desc['source_binding_sha256']==frozen['source_binding_sha256'], 'POST_BINDING')
    # These actual post source bytes are retained separately from the original
    # package. Only the repaired guest helper differs; there is no arbitrary
    # replacement of transport, target, plan or core implementation.
    post_sources = dict(sources)
    packed = base64.b64decode(receipt['post_guest_source'],validate=True)
    require(len(packed)<=65536,'POST_SOURCE_BOUND')
    decoder=zlib.decompressobj()
    post_source=decoder.decompress(packed,196609)
    require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail
        and len(post_source)<=196608,'POST_SOURCE_BOUND')
    require(pin(post_source)==dict(bytes=103400,sha256=
        'd23f88a47def91684556afd06c8f986a38ece0834575206b429d47b2e2ebf426'), 'POST_REPAIR_SOURCE')
    post_sources['q2_journal_growth_guest.py'] = post_source
    require(start['post_sources']=={n:pin(b) for n,b in post_sources.items()}
        and start['ssh_argv_sha256']==h.digest(h.canonical(h.remote_argv(frozen['anchor_path'],post_sources,post_desc))), 'POST_SOURCE')
    transport = completed['transport']
    require(completed['state']=='POST_CONTINUATION_VERIFIED' and completed['new_ssh_calls']==1
        and completed['old_failure_sha256']==start['original_failure_sha256']
        and transport['returncode']==0 and transport['eof']==dict(stdout=True,stderr=True), 'POST_COMPLETION')
    require(transport['files']=={n:pin(raw['post.'+n]) for n in ('stdout','stderr')}
        and completed['ssh_process']['exit']==0 and completed['ssh_process']['vm'] is False, 'POST_STREAM_BINDING')
    pre_transport = results['POWERED_OFF']['transport']
    require(results['POWERED_OFF']['pidfd_exit'] is True and pre_transport['returncode'] in (0,255)
        and pre_transport['eof']==dict(stdout=True,stderr=True)
        and pre_transport['files']=={n:pin(raw['pre.'+n]) for n in ('stdout','stderr')}
        and pre_transport['ack']==ack and ack['pre_report_sha256']==h.digest(h.canonical(pre)), 'NORMAL_SHUTDOWN')
    original,restart = manifest['original_argv'],start['argv']
    expected_restart = list(manifest['restart_argv']);expected_restart[0]='qemu-system-x86_64'
    require(manifest['restart_argv'][0]=='/usr/bin/qemu-system-x86_64'
        and restart==expected_restart and start['passive_elapsed_seconds']>=60
        and all(start[n]==0 for n in ('repeated_shutdowns','repeated_backups','repeated_image_growth','repeated_starts')), 'RESTART')
    new = completed['new_vm']
    require(new==start['vm'] and new['argv_sha256']==h.digest(b'\0'.join(w.encode() for w in restart)+b'\0')
        and raw['vm.pid'].strip()==str(new['pid']).encode(), 'VM_IDENTITY')
    for stage,size in (('POWERED_OFF',g.OLD_SIZE),('IMAGE_GROWN',g.NEW_SIZE)):
        image=results[stage]['image'] if stage=='POWERED_OFF' else results[stage]
        h.validate_image_info(h.canonical(image['info']),size)
        require(image['check_returncode']==0 and image['check_eof']==dict(stdout=True,stderr=True)
            and all(image['check'].get(k,0)==0 for k in ('check-errors','corruptions','leaks')), 'IMAGE_CHECK')
    require(results['IMAGE_GROWN']['logical_compare']==dict(returncode=0,eof=dict(stdout=True,stderr=True)), 'IMAGE_CONTENT')
    g.verify_preservation(pre['tree'],post['tree']);g.validate_completion(pre['rows'],post['rows'])
    comparison=h.prior.compare(dict(rows=post['rows']),frozen['horizon'])
    require(completed['comparison']==comparison and all(row[k]['deficit']==0
        for row in comparison['pools'] for k in ('bytes','inodes')), 'CAPACITY')
    p.validate_retained_custody(old['retained_custody'],implementation=implementation,
        nonce=marker['nonce'],source_files=manifest['sources'])
    require(old['retained_custody']['originals']==frozen['previous_maintenance_identities']
        and receipt['history_recheck']=='REOPENED_AND_RECHECKED', 'RETAINED_HISTORY')
    p.validate_coordinator_completion(completion,old['retained_custody'])
    require(completion['receipt_sha256']==h.digest(raw['receipt.json']), 'FINAL_RECEIPT')
    journal=next(row for row in post['rows'] if row['role']=='journal')
    value=dict(schema='local-hand-q2-core-journal-transition/v23',authority={k:manifest[k] for k in ('R','A','C')},
        implementation=copy.deepcopy(implementation),session=h.SESSION,nonce=marker['nonce'],
        persistent_source=copy.deepcopy(frozen['source_binding']['persistent_source']),
        local_preflight_source=local_source,transport_failure_source=failed_source,
        retained_custody=copy.deepcopy(old['retained_custody']),coordinator_completion=completion,
        runtime_parent_binding=copy.deepcopy(frozen['runtime_parent_binding']),
        runtime_preparation={phase:g.runtime_summary(report) for phase,report in (('pre',pre),('post',post))},
        guest_startup_assurance=g.guest_startup_assurance(),previous_maintenance=p.build_previous_maintenance(frozen['previous_maintenance_files']),
        access_mode='TRUSTED_SINGLE_ADMIN',host_writer_observation='NOT_PERFORMED',continuous_exclusion_proven=False,
        input_sha256=desc['source_binding_sha256'],manifest_sha256=marker['manifest_sha256'],source_files=manifest['sources'],
        originals=[dict(basename='.'+h.SESSION+'.'+name,**pin(b)) for name,b in sorted(raw.items())],
        old_boot_id=pre['boot_id'],new_boot_id=post['boot_id'],vm_activation=frozen['vm_activation'],
        old_vm=manifest['vm'],new_vm=new,image_identities=manifest['image_identities'],old_pidfd_exited=True,
        original_argv_sha256=h.digest(h.canonical(original)),restart_argv_sha256=h.digest(h.canonical(restart)),
        backup=results['BACKED_UP'],virtual_bytes=dict(before=g.OLD_SIZE,after=g.NEW_SIZE),
        filesystem=dict(uuid=journal['filesystem']['uuid'],before_bytes=pre['journal_device']['superblock']['filesystem_bytes'],
            after_bytes=post['journal_device']['superblock']['filesystem_bytes'],available=journal['available']),
        content={k:post['tree'][k] for k in ('entries','content_bytes','sha256')},
        reports={phase:pin(h.canonical(report)) for phase,report in (('pre',pre),('post',post))},
        completed_steps=list(h.STATES[1:]),transport_exits=[pre_transport['returncode'],transport['returncode']],
        image_checks=[0,0],logical_compare_exit=0,resize_exit=post['resize_result']['returncode'],all_streams_eof=True,
        historical_exit='UNKNOWN',old_commitments_refunded=False)
    value['retained_identity']=dict(schema='lhq-retained-quota-identity/v1',source_plan_sha256=p.RETAINED_PLAN_SHA,
        roots_sha256=g.RETAINED_QUOTA_SHA,pre=g.retained_sample(pre,desc),post=g.retained_sample(post,desc),reports=value['reports'])
    return p.validate_journal_transition(value,priors=priors,implementation=implementation)
