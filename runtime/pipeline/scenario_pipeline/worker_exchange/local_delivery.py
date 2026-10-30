"""Local-only, model-free adoption of a worker delivery assignment.

The portable worker provides JSON proposals; only this module knows Store or
the authoritative run database. No CARLA execution happens here.
"""
import json
import hashlib
from pathlib import Path

from .common import read, sha, write
from .branch_coverage import assignment_path, assignments
from .local import adopt, freeze, prepare_manifest_jobs


def _selection_targets(root, assignment):
    targets = assignment.get('selection_targets')
    if not targets:
        role = assignment.get('role') or assignment['assignment_id'].split('__',1)[0]
        targets = {'training': ['full-train'], 'testing': ['demo-test', 'full-test'],
                   'heldout': ['held-out']}[role]
    targets = list(targets)
    if len(targets) != len(set(targets)) or not targets:
        raise ValueError('Invalid delivery selection targets')
    identity = (assignment['law_id'], assignment['cell_id'], assignment['actor'])
    for sid in targets:
        scope = read(Path(root)/'sets'/sid/'scope.json')
        if not any((row.get('law_id'),row.get('cell_id'),row.get('actor')) == identity
                   for row in scope['assignments']):
            raise ValueError('Delivery assignment absent from '+sid+' scope')
    return targets


def _same_file(path, value):
    path = Path(path)
    if path.exists():
        if read(path) != value:
            raise ValueError('Frozen local delivery input changed: '+str(path))
    else:
        write(path, value)
    return path


def _job(store, run, stage, entity, actor):
    rows = [dict(row) for row in store.db.execute(
        "SELECT j.* FROM jobs j JOIN run_jobs r ON r.job_id=j.id "
        "WHERE r.run_id=? AND r.active=1 AND j.stage=? AND j.entity=? AND j.actor=?",
        (run, stage, entity, actor))]
    if len(rows) != 1:
        raise ValueError('Missing or ambiguous '+stage+' job: '+entity)
    return rows[0]


def _adopt(root, repo, batch, db, run, aid, job, proposal):
    plan = {'assignment_id': aid, 'proposal': proposal, 'job_id': job['id'],
            'expected_cache_key': job['cache_key']}
    path = _same_file(Path(root)/'state/operations/worker_exchange'/batch/'stage-plans'/
                      (str(job['id'])+'.json'), plan)
    return adopt(root, repo, batch, db, run, path)


def prepare(root, repo, batch, db, assignment_id, case_id, candidate_id='primary'):
    """Freeze one-law inputs and adopt every semantic/construction job exactly.

    A repeat invocation resumes the same run and verifies existing artifacts.
    Execution remains a separate GPU-owned operation.
    """
    from batch_pipeline.store import Store
    from batch_pipeline import stages
    from batch_pipeline.run_inputs import freeze_job_revision
    from .exchange import check_return, import_return
    from .semantic_delivery import validate as validate_semantic
    from .execution_manifest import validate as validate_manifest
    import pipeline

    root, repo, db = (Path(value).resolve() for value in (root, repo, db))
    if db.parent != root/'state':
        raise ValueError('Delivery database belongs directly under artifact state/')
    checked = check_return(root, repo, batch)
    imported = import_return(root, repo, batch)
    if assignment_id not in imported['destinations']:
        raise ValueError('Unknown imported delivery assignment')
    item = assignments(repo, read(repo/'batch.json'))[assignment_id]
    assignment = read(assignment_path(repo, assignment_id, item))
    folder = repo/'work'/assignment_id
    manifest = validate_manifest(repo, assignment_id)
    validate_semantic(folder, assignment, manifest)
    entry = next((item for item in manifest['cases'] if item['case_id']==case_id),None)
    if entry is None or entry['kind']!='delivery':
        raise ValueError('Select one exact delivery case')
    from .candidate_constructions import select
    select(folder/'execution-manifest.json',case_id,candidate_id)
    _selection_targets(root, assignment)

    case_key=hashlib.sha256((case_id+'|'+candidate_id).encode()).hexdigest()[:16]
    run = 'worker-delivery-'+assignment['cell_id']+'-'+assignment['law_id']+'-'+assignment['actor']+'-'+case_key
    local = root/'inputs/worker_exchange'/batch/'local-run-inputs'/assignment_id
    law_path = local/'laws.jsonl'
    summary_path = local/'summaries.jsonl'
    if not isinstance(assignment.get('summary'),dict) or assignment['summary'].get('id') != assignment['law_id']:
        raise ValueError('Missing exact worker assignment law summary')
    for path, value in ((law_path, assignment['law']), (summary_path, assignment['summary'])):
        content = json.dumps(value,sort_keys=True)+'\n'
        if path.exists() and path.read_text() != content:
            raise ValueError('Frozen law input changed: '+str(path))
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():path.write_text(content)
    context = {'project_root': str(Path(__file__).resolve().parents[2]),
               'resource_paths': [str(Path(__file__).resolve().parents[2]/name)
                                  for name in ('carla','envs','scripts')],
               'policy': 'Local simulator resources; inspect before each owned execution'}
    context_path = _same_file(local/'simulator-context.json', context)
    output = root/'state/operations/worker_exchange'/batch/'local-runs'/assignment_id/case_key
    store = Store(db)
    try:
        if not store.db.execute('SELECT 1 FROM runs WHERE id=?',(run,)).fetchone():
            catalog_id = pipeline.import_catalog(store,root/'inputs/catalog/vocabulary_catalog.json')
            pipeline.create_run(store,run,catalog_id,output,summary_path,[],
                                'worker-exchange-reviewed',simulator_context=context_path,laws=law_path)
        info = stages.run_info(store,run)
        if set(info['config'].get('law_scope',{}).get('records',{})) != {assignment['law_id']}:
            raise ValueError('Delivery run law scope differs from assignment')
        catalog = stages.catalog(store,run)
        config = dict(info['config'], worker_delivery_selection={
            'case_id':case_id,'candidate_id':candidate_id})
        base = freeze_job_revision(store,run,catalog,config,
            {'worker_exchange_package': checked['package_sha256'],
             'assignment_id': assignment_id, 'role': 'base_for_fresh_delivery_child'})
    finally:
        store.db.close()
    config_path = _same_file(local/('reviewed-config-'+case_key+'.json'),config)
    revision = freeze(root,repo,batch,db,run,base,config_path,
                      assignment_ids=[assignment_id])['input_revision']

    index = read(folder/'proposals/semantic-index.json')['stages']
    cell, actor, law = assignment['cell'], assignment['actor'], assignment['law_id']
    store = Store(db)
    try:
        batch_id = stages.enqueue(store,run,'relevance_batch',cell['cell_id']+':batch:0',actor,
            {'cell':cell,'actor':actor,'law_ids':[law],'input_revision':revision})
        batch_job = store.job(batch_id)
    finally:store.db.close()
    _adopt(root,repo,batch,db,run,assignment_id,batch_job,index['relevance_batch']['path'])
    store=Store(db)
    try:
        relevance_id=stages.enqueue(store,run,'relevance',cell['cell_id'],actor,
            {'cell':cell,'actor':actor,'input_revision':revision},[batch_id])
        relevance_job=store.job(relevance_id)
    finally:store.db.close()
    _adopt(root,repo,batch,db,run,assignment_id,relevance_job,index['relevance']['path'])
    store=Store(db)
    try:template_job=_job(store,run,'template',law+'@'+actor,actor)
    finally:store.db.close()
    _adopt(root,repo,batch,db,run,assignment_id,template_job,index['template']['path'])

    for reference in index['judgment_observables']:
        proposal=read(folder/reference['path'])
        store=Store(db)
        try:
            rows=[dict(row) for row in store.db.execute(
                "SELECT j.* FROM jobs j JOIN run_jobs r ON r.job_id=j.id "
                "WHERE r.run_id=? AND r.active=1 AND j.stage='judgment_observables' AND j.actor=?",
                (run,actor)) if json.loads(row['payload']).get('phrase')==proposal['phrase']
                and json.loads(row['payload']).get('note','')==proposal.get('note','')]
            if len(rows)!=1:raise ValueError('Missing exact judgment observables job')
            job=rows[0]
        finally:store.db.close()
        _adopt(root,repo,batch,db,run,assignment_id,job,reference['path'])

    store=Store(db)
    try:
        parents=[relevance_id,template_job['id']]
        parents.extend(row[0] for row in store.db.execute(
            "SELECT j.id FROM jobs j JOIN run_jobs r ON r.job_id=j.id "
            "WHERE r.run_id=? AND r.active=1 AND j.stage='judgment_observables' AND j.actor=?",
            (run,actor)))
        binding_id=stages.enqueue(store,run,'bindings',cell['cell_id'],actor,
            {'cell':cell,'actor':actor,'template_ids':[law+'@'+actor],
             'explicit_contexts':[],'context_predicates':{},'input_revision':revision},parents)
        binding_job=store.job(binding_id)
    finally:store.db.close()
    _adopt(root,repo,batch,db,run,assignment_id,binding_job,index['bindings']['path'])
    store=Store(db)
    try:cases_job=_job(store,run,'cases',cell['cell_id'],actor)
    finally:store.db.close()
    _adopt(root,repo,batch,db,run,assignment_id,cases_job,index['cases']['path'])
    jobs=prepare_manifest_jobs(root,repo,batch,db,run,assignment_id,cases_job['id'],
                               [case_id],{case_id:candidate_id})
    receipt={'assignment_id':assignment_id,'case_id':case_id,'candidate_id':candidate_id,
             'run':run,'db':str(db),'input_revision':revision,
             'package_sha256':checked['package_sha256'],'semantic_jobs_completed':True,
             'execution_job_ids':jobs['exact_execution_job_ids'],
             'native_dispatched':False,'recordings_accepted':0}
    _same_file(root/'state/operations/worker_exchange'/batch/'prepared'/
               (assignment_id+'-'+case_key+'.json'),receipt)
    return receipt


def execute_exact(root, repo, batch, db, run, assignment_id, case_id, job_id,
                  python, host, port, timeout=3600):
    """Dispatch only one prepared canonical execution job to an operator-owned server."""
    from batch_pipeline.store import Store
    from batch_pipeline.engines import execute_pool
    from .exchange import check_return
    from .branch_coverage import assignments, assignment_path
    root, repo, db = (Path(value).resolve() for value in (root,repo,db))
    if db.parent != root/'state':
        raise ValueError('Delivery database belongs under state/')
    check_return(root,repo,batch)
    assignment=read(assignment_path(repo,assignment_id,
                    assignments(repo,read(repo/'batch.json'))[assignment_id]))
    store=Store(db)
    try:
        job=store.job(job_id)
        if not job or job['stage']!='execution' or job['status'] not in ('pending','failed'):
            raise ValueError('Select one pending or failed canonical execution job')
        if not store.db.execute('SELECT 1 FROM run_jobs WHERE run_id=? AND job_id=? AND active=1',
                                (run,job_id)).fetchone():
            raise ValueError('Execution job is not active in selected run')
        request=json.loads(job['payload'])
        if (request.get('case',{}).get('case_id')!=case_id or job['actor']!=assignment['actor']
                or request.get('cell',{}).get('cell_id')!=assignment['cell_id']
                or request.get('case',{}).get('target_law_id')!=assignment['law_id']):
            raise ValueError('Execution job differs from selected worker case')
        engine={'id':'worker-delivery-exact','python':str(Path(python).resolve()),
                'host':host,'port':int(port),'allow_login_node':True}
        result=execute_pool(store,run,[engine],timeout=timeout,job_ids=(job_id,))
        return {'run':run,'job_id':job_id,'case_id':case_id,'result':result,
                'status':store.job(job_id)['status']}
    finally:store.db.close()


def accept(root, repo, batch, db, run, assignment_id, case_id, job_id, attempt_number,
           audit_path):
    """Accept one completed canonical attempt after independent saved audit.

    This never drives CARLA or edits the frozen worker return. It appends the
    same recording identity to both testing selections, idempotently.
    """
    from contextlib import ExitStack
    from batch_pipeline.store import Store, atomic
    from batch_pipeline.completion import verify as verify_completion
    from recording_store import (stored_attempt_path, accept_recording,
                                 verify_recording, locked, sha as file_sha)
    from .delivery_handoff import CHECKS, validate_case
    from .execution_manifest import validate as validate_manifest
    root, repo, db, audit_path = (Path(value).resolve() for value in (root,repo,db,audit_path))
    if db.parent != root/'state':raise ValueError('Wrong local delivery database location')
    manifest=validate_manifest(repo,assignment_id)
    entry=next((item for item in manifest['cases'] if item['case_id']==case_id),None)
    if entry is None or entry['kind']!='delivery':raise ValueError('Not an exact delivery case')
    assignment=read(assignment_path(repo,assignment_id,
                    assignments(repo,read(repo/'batch.json'))[assignment_id]))
    role=assignment.get('role') or assignment_id.split('__',1)[0]
    targets=_selection_targets(root, assignment)
    validate_case(repo/'work'/assignment_id,entry,targets)
    store=Store(db)
    try:
        job=store.job(job_id)
        if not job or job['stage']!='execution' or job['status']!='completed':
            raise ValueError('Exact canonical execution job is not completed')
        if not store.db.execute('SELECT 1 FROM run_jobs WHERE run_id=? AND job_id=? AND active=1',
                                (run,job_id)).fetchone():
            raise ValueError('Execution job is not active in delivery run')
        request=json.loads(job['payload'])
        if (request.get('case',{}).get('case_id')!=case_id
                or request.get('cell',{}).get('cell_id')!=assignment['cell_id']
                or job['actor']!=assignment['actor']
                or request.get('case',{}).get('target_law_id')!=assignment['law_id']):
            raise ValueError('Execution job differs from worker delivery identity')
        if job['attempts']!=attempt_number:
            raise ValueError('Select exact completed attempt number')
        attempt=stored_attempt_path(store,job_id,attempt_number).resolve()
        observed=store.artifact(job['artifact_id'])['payload']
        verify_completion(attempt,observed['completion']['binding'])
    finally:store.db.close()
    folder=attempt.parent
    if folder != root/'recordings'/folder.name or attempt not in audit_path.parents:
        raise ValueError('Audit and attempt must belong to one canonical recording')
    audit=read(audit_path)
    if (audit.get('format')!='worker-delivery-audit-v1' or audit.get('passed') is not True
            or audit.get('case_id')!=case_id or audit.get('job_id')!=job_id
            or audit.get('attempt')!=attempt_number or audit.get('recording_id')!=folder.name
            or not CHECKS <= {key for key,value in audit.get('checks',{}).items() if value is True}):
        raise ValueError('Independent delivery audit incomplete or for another attempt')
    if file_sha(attempt/'result.json')!=audit.get('source_result_sha256'):
        raise ValueError('Audit does not bind the sealed Native result')
    video=(attempt/audit['video']).resolve();trace=(attempt/audit['trace']).resolve()
    if attempt not in video.parents or attempt not in trace.parents:
        raise ValueError('Audit output escapes the canonical attempt')
    if file_sha(video)!=audit.get('video_sha256') or file_sha(trace)!=audit.get('trace_sha256'):
        raise ValueError('Audited video or Core trace changed')
    scenes=read(trace)['scenes']
    if len(scenes)!=audit.get('frames') or audit['frames']<1:
        raise ValueError('Core scene count differs from audited original frames')
    with (attempt/'video_frames.jsonl').open() as source:
        for index,line in enumerate(source):
            if index>=len(scenes):raise ValueError('Original frame map exceeds Core trace')
            frame=json.loads(line)
            if frame.get('video_frame')!=index or scenes[index]['t']!=round(frame['time_s']*1000):
                raise ValueError('Original frame/Core timestamp join failed')
        if index+1!=len(scenes):raise ValueError('Core trace exceeds original frame map')
    from .media import audit as decode_video
    decode_video(video,len(scenes),threads=4,receipt=attempt/'delivery-primary-decode.json')
    record={'law_id':assignment['law_id'],'frames':len(scenes),
            'video_source':str(video),'video_sha256':audit['video_sha256'],
            'trace_source':str(trace),'trace_sha256':audit['trace_sha256'],
            'delivery_audit':str(audit_path),'delivery_audit_sha256':file_sha(audit_path),
            'split':role,'case_id':case_id,'cell_id':assignment['cell_id'],
            'actor':assignment['actor']}
    rid=accept_recording(attempt,record)
    verify_recording(folder)
    member={'campaign':run,'cell_id':assignment['cell_id'],'actor':assignment['actor'],
            'case_id':case_id,'law_id':assignment['law_id'],'split':role,
            'status':'accepted','recording_id':rid}
    version=root/'inputs/worker_exchange'/batch/'selection-versions'/rid
    with ExitStack() as stack:
        for sid in targets:
            stack.enter_context(locked(root/'state'/('set-'+sid+'.lock')))
        updates={}
        for sid in targets:
            path=root/'sets'/sid/'selection.json';current=read(path)
            if not current.get('frozen'):
                raise ValueError('Delivery selection is not frozen')
            if any(row.get('case_id')==case_id and row.get('law_id')==assignment['law_id']
                   and row.get('cell_id')==assignment['cell_id']
                   and row.get('recording_id')!=rid for row in current['members']):
                raise ValueError('Case already selected with another recording')
            if member in current['members']:
                updates[sid]=None;continue
            next_value=dict(current,members=[*current['members'],member],
                            selection_version='worker-delivery-'+batch+'-'+rid[:12])
            updates[sid]=(path,current,next_value)
        for sid,item in updates.items():
            if item is None:continue
            path,before,after=item
            _same_file(version/(sid+'-before.json'),before)
            _same_file(version/(sid+'-after.json'),after)
            atomic(path,after)
    from organize_work import refresh_workspaces
    refresh_workspaces(root)
    return {'recording_id':rid,'case_id':case_id,'job_id':job_id,'attempt':attempt_number,
            'accepted_in':targets,'audit_sha256':file_sha(audit_path)}
