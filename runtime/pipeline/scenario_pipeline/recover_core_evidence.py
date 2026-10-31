"""Saved-only forensic inventory; never treats another law's labels as evidence."""
from collections import Counter
import gc
import json
from pathlib import Path
from recording_store import identity, sha
from batch_pipeline.store import atomic


def audit_recovery(root,package,held_ids,core_ids):
    root=Path(root);package=Path(package)
    members=json.loads((root/'sets/held-out/selection.json').read_text())['members']
    excluded=[m for m in members if m['law_id'] not in core_ids]
    inventory=[]
    for number,member in enumerate(excluded):
        rid=member['recording_id'];folder=root/'recordings'/rid;evidence=folder/'evidence'
        meta=json.loads((folder/'metadata.json').read_text());checks={};issues=[]
        # Stream hashes and process a single trace at a time; no native replay.
        for name,key in (('video.webm','video_sha256'),('trace.json','trace_sha256')):
            checks[name]=sha(folder/name)==meta[key]
            if not checks[name]:issues.append('Primary '+name+' differs from preserved acceptance hash')
        def load(name):
            path=evidence/name
            return json.loads(path.read_text()) if path.exists() else {}
        result=load('result.json');acceptance=load('acceptance_receipt.json');measured=load('measured_review.json')
        native={};video=[]
        for filename,target in (('trace.jsonl',native),('video_frames.jsonl',video)):
            path=evidence/filename
            if not path.exists():issues.append('Missing '+filename);continue
            with path.open() as stream:
                for line in stream:
                    value=json.loads(line)
                    if isinstance(target,dict):target[value['frame']]=value
                    else:target.append(value)
        checks['full_native_video_join']=len(native)==len(video)==int(meta['frames']) and all(
            v['carla_frame'] in native and abs(v['time_s']-native[v['carla_frame']]['time_s'])<1e-6 for v in video)
        checks['complete_original']=result.get('complete') is True and result.get('frames')==int(meta['frames'])
        checks['actual_controls_present']=all(row.get('control') is not None for row in native.values()) and bool(native)
        core=json.loads((folder/'trace.json').read_text());scenes=core.get('scenes',[])
        checks['core_time_join']=len(scenes)==len(video) and all(s['t']==round(v['time_s']*1000) for s,v in zip(scenes,video))
        checks['subject_identity_join']=all(s.get('subject')==result.get('native_subject_actor_id') for s in scenes)
        del scenes,core;gc.collect()
        for check,passed in checks.items():
            if not passed:issues.append(check+' failed')
        law=member['law_id']
        if law=='NRS-484B-630-1':
            classification='saved_only_adaptation_required';targets=['NRS-484B-623-1']
            reason='Actual motor-vehicle slow-driving, follower trajectories, observed controls and turnout histories support a minimum-speed/traffic-flow case; normal/reasonable flow and safety exceptions remain unresolved.'
        elif law.startswith('LVMC-11-22-150-'):
            classification='saved_only_adaptation_required';targets=['NRS-484B-600-1b']
            reason='Actual motor-vehicle speed and nearby-participant observations can support endangerment observations without importing the old 15-mph threshold or prudent-speed label.'
        elif law=='NRS-484B-637-2b':
            classification='partial_supporting_evidence';targets=['NRS-484B-600-1b']
            reason='Motor-vehicle motion is retained, but eight-second histories, synthetic classification/registration and native-versus-authored posting differences need target-specific resolution.'
        else:
            classification='partial_supporting_evidence';targets=[]
            reason='Preserve crossing, signal, clearance and counterpart evidence. PDD/MCD subject identity cannot be substituted for a core driver/cyclist/pedestrian; any counterpart use needs an independent subject audit.'
        if issues:classification='partial_supporting_evidence'
        candidate_reviews=[{'law_id':law_id,'source_actor_unchanged':True,'scope':'conditional observation reuse only',
                            'required_before_acceptance':['Review exact target-law requirements and applicability against recorded context',
                              'Freeze a target-specific case and historical-duration justification',
                              'Preserve unknown judgment standards and remove inherited source-law labels',
                              'Create saved-only Core/context/video derivation if target-specific captions differ',
                              'Validate source/native/Core/video joins and issue immutable reuse receipt'],
                            'new_target_accepted':False} for law_id in targets if law_id in core_ids]
        native_path=evidence/'trace.jsonl'
        entry={'recording_id':rid,'source_member':member,'source_law_id':law,'frames':meta['frames'],
               'video_sha256':meta['video_sha256'],'trace_sha256':meta['trace_sha256'],
               'source_acceptance_sha256':sha(evidence/'acceptance_receipt.json') if acceptance else None,
               'legacy_acceptance_status':acceptance.get('status'),'source_native_complete':result.get('complete'),
               'source_attempt':meta.get('published_record',{}).get('source_attempt'),
               'native_trace_sha256':sha(native_path) if native_path.exists() else None,
               'native_subject_actor_id':result.get('native_subject_actor_id'),
               'source_configuration_sha256':result.get('configuration_sha256'),
               'checks':checks,'findings':issues,'classification':classification,'reason':reason,
               'measured_review':measured,'source_limitations':meta.get('published_record',{}).get('not_testable_from_this_video',[]),
               'candidate_reuse_reviews':candidate_reviews,'core_acceptance':'not_claimed',
               'video_decode':'Historical acceptance retained; current primary hash and frame joins checked, no new decode claimed',
               'new_native_episode':False}
        inventory.append(entry)
        if number%10==0:print(json.dumps({'phase':'saved-recovery-audit','pairs':number+1,'total':len(excluded)}),flush=True)
    groups=Counter(e['native_trace_sha256'] for e in inventory if e['native_trace_sha256'])
    summary={'pairs':len(inventory),'classifications':dict(Counter(e['classification'] for e in inventory)),
             'source_laws':dict(Counter(e['source_law_id'] for e in inventory)),
             'distinct_native_trace_hashes':len(groups),'duplicate_native_trace_groups':[h for h,n in groups.items() if n>1],
             'source_findings':sum(bool(e['findings']) for e in inventory),'new_core_pairs_accepted':0,'native_executions':0,
             'excluded_laws_added_to_corpus':0,'inventory':'recovery-inventory.json'}
    package.mkdir(parents=True,exist_ok=True)
    for name,value in (('recovery-inventory.json',inventory),('recovery-summary.json',summary)):
        path=package/name
        if path.exists() and json.loads(path.read_text())!=value:raise ValueError('Recovery audit changed; retain and version prior report')
        if not path.exists():atomic(path,value)
    return summary


def review_generic_motor_reuse(root,package,project):
    """Refine narrow source-law gaps against an actual broader core obligation."""
    root=Path(root);package=Path(package);project=Path(project)
    baseline=package/'recovery-inventory.json'
    inventory=json.loads(baseline.read_text())
    lawfile=project/'repo_prep/nevada_sydney/pipeline/traffic-spec-agent/laws/full_list/laws.jsonl'
    laws={r['id']:r for r in (json.loads(s) for s in lawfile.read_text().splitlines() if s.strip())}
    target=laws['NRS-484B-600-1b'];updated=[]
    for row in inventory:
        if row['source_law_id']!='NRS-484B-637-2b':continue
        folder=root/'recordings'/row['recording_id']
        if row['source_member']['actor']!='motor_vehicle_driver' or row['findings']:continue
        if sha(folder/'trace.json')!=row['trace_sha256']:raise ValueError('Source Core changed since recovery audit')
        core=json.loads((folder/'trace.json').read_text())
        class_ok=all(any(u['track']==s['subject'] and 'motor_vehicle' in u.get('classes',[]) for u in s['users']) for s in core['scenes'])
        del core;gc.collect()
        if not class_ok:continue
        row['classification']='saved_only_adaptation_required'
        row['reason']='Per-target review: 600-1b governs operation of a vehicle of any kind. Native/Core motor-vehicle identity, controls and motion are present. Low-speed certification, registration and the old synthetic posted limit are not conditions of this target and must not be inherited as conclusions.'
        row['target_requirement_review']={
            'law_id':target['id'],'quote':target['text'],'law_record_sha256':identity(target),
            'subject':'Original motor_vehicle_driver and Core motor_vehicle class preserved in every frame',
            'operation':'Original controls, speed and motion checked in the native/video/Core joins',
            'context':'Retain original surrounding bodies, recorded scene and explicit assumptions',
            'time_scope':'Only the original eight-second sampled window; no unrecorded approach or outcome claimed',
            'endangerment':'Unresolved judgment; no speed cutoff or new verdict assigned',
            'unneeded_for_target':['Low-speed certification','Vehicle registration','The old numerical posting'],
            'remaining':['Freeze and accept a target-specific saved-only derivation','Replace source-law captions/labels with qualified observation-only presentation'],
            'new_target_accepted':False}
        updated.append(row['recording_id'])
    report={'version':'recovery-review-v2','base_inventory':'recovery-inventory.json','base_inventory_sha256':sha(baseline),
            'pairs':len(inventory),'reclassified_pairs':updated,'classifications':dict(Counter(e['classification'] for e in inventory)),
            'new_core_pairs_accepted':0,'native_executions':0,'source_pairs_preserved':True,'inventory':inventory}
    path=package/'recovery-review-v2.json'
    if path.exists() and json.loads(path.read_text())!=report:raise ValueError('Versioned recovery review changed')
    if not path.exists():atomic(path,report)
    return {k:v for k,v in report.items() if k!='inventory'}
