"""Diagnosed reconstruction in the same run; never replay for a favorable label."""
import asyncio
import json
from pathlib import Path

from . import stages
from .runner import run
from .store import digest


def validate_repair(result, request):
    context = request.get('repair_context')
    if not context:
        return
    repair = result.get('repair',{})
    if not repair.get('diagnosis') or not repair.get('evidence_references'):
        raise ValueError('Repair needs an evidence-backed diagnosis')
    if not set(repair['evidence_references']) <= set(context['evidence_files']):
        raise ValueError('Repair diagnosis references evidence outside the failed attempt')
    if repair.get('approved_case_sha256') != digest(request['case']):
        raise ValueError('Repair changed or failed to bind the approved case and targets')
    plan=context['previous_construction'].get('measurement_plan')
    if plan is not None and result.get('measurement_plan')!=plan:
        raise ValueError('Repair must preserve the approved measurement plan and tolerances')
    old = {f['path']:f['content'] for f in context['previous_construction']['files']}
    new = {f['path']:f['content'] for f in result['files']}
    changed = sorted(k for k in set(old)|set(new) if old.get(k)!=new.get(k))
    if not changed or sorted(repair.get('changed_files',[])) != changed:
        raise ValueError('Repair must identify an actual construction change, not replay the same recording')
    if repair.get('scope') not in ('capture','controller_implementation','reporting','realize_approved_setup'):
        raise ValueError('Repair requires authorization to change scenario scope or targets')


def repair_identity_request(request):
    """Ignore only scheduler-generated feedback when matching the same repair."""
    value=json.loads(json.dumps(request))
    context=value.get('repair_context')
    if isinstance(context,dict):
        context['evidence_files']={path:sha for path,sha in context.get('evidence_files',{}).items()
                                   if Path(path).name!='delivery_repair_failure.json'}
        # These wrappers report the same retained runtime failure and do not
        # add physical evidence. Preserve every supplied request verbatim;
        # this normalization affects only matching an existing repair.
        failure=context.get('failure')
        retained=context.get('retained_result')
        if isinstance(failure,dict) and isinstance(retained,dict) and retained.get('error'):
            summary=failure.get('error','')
            if isinstance(summary,str) and summary.startswith((
                    'Execution worker failed; retained logs:',
                    'Recovery rejected: Missing or mismatched atomic completion binding')):
                failure.pop('error',None)
    return value


def schedule_repair(store, run_id, execution_job, failure, *, timeout=900, limiter=None):
    """Generate a diagnosed construction and execute it through the normal executor."""
    execution = store.job(execution_job)
    parent = store.db.execute("SELECT j.* FROM dependencies d JOIN jobs j ON j.id=d.dependency_id WHERE d.job_id=? AND j.stage='construction'",(execution_job,)).fetchone()
    if parent is None or parent['status']!='completed':
        raise ValueError('Repair requires the failed case\'s completed construction')
    request = json.loads(parent['payload'])
    previous = store.artifact(parent['artifact_id'])['payload']
    attempt = Path(failure['execution'])
    comparisons=[];observed=None
    if (attempt/'result.json').is_file():
        observed=json.loads((attempt/'result.json').read_text())
        comparisons=[{k:c[k] for k in ('target','requested','tolerance')} for c in observed.get('target_checks',[])
                     if isinstance(c.get('target'),str) and all(k in c for k in ('requested','tolerance'))]
    evidence = {str(p):digest(p.read_text()) for p in attempt.glob('*.json') if p.name!='construction.json'}
    for path in attempt.glob('*.log'):
        evidence[str(path)] = digest(path.read_text(errors='replace'))
    if not evidence:
        raise ValueError('Repair requires retained diagnostic evidence')
    request['repair_context'] = {'failed_execution_job':execution_job,'attempt':str(attempt),
        'failure':failure,'evidence_files':evidence,'previous_construction':previous,
        'retained_result':observed,
        'retained_logs':{str(path):path.read_text(errors='replace') for path in attempt.glob('*.log')},
        'approved_case_sha256':digest(request['case']),
        'policy':'Use retained_result and retained_logs as the exact readable evidence from this failed attempt; evidence_files hashes retain provenance and are not substitutes for measurements. Diagnose and change capture, controller implementation, reporting, or realization of the approved setup. Preserve case IDs, target values, tolerances, law, scope, and fixed comparisons. Never rerun unchanged code for a favorable outcome.'}
    deps = [r[0] for r in store.db.execute('SELECT dependency_id FROM dependencies WHERE job_id=?',(parent['id'],))]
    config=stages.run_info(store,run_id)['config']
    matching_request=dict(request,model_config=config.get('model',{}))
    if config.get('run_inputs_version'):
        matching_request['run_inputs_version']=config['run_inputs_version']
    identity=digest(repair_identity_request(matching_request))
    construction=None
    for candidate in store.db.execute(
            "SELECT j.id,j.payload,j.status FROM jobs j JOIN run_jobs r ON r.job_id=j.id "
            "WHERE r.run_id=? AND r.active=1 AND j.stage='construction' AND j.entity=? AND j.actor=? "
            "ORDER BY j.id DESC",(run_id,parent['entity'],parent['actor'])):
        if digest(repair_identity_request(json.loads(candidate['payload'])))==identity:
            if candidate['status']=='running':
                raise ValueError('Existing diagnosed construction repair is still running; retain its owner and do not duplicate it')
            construction=candidate['id']
            break
    if construction is None:
        with store.transaction():
            construction = stages.enqueue(store,run_id,'construction',parent['entity'],parent['actor'],request,deps)
    command = config['model']['worker_argv']
    asyncio.run(run(store,run_id,command,concurrency=1,timeout=timeout,stage_names=('construction',),job_ids=(construction,),limiter=limiter))
    job = store.job(construction)
    if job['status']!='completed':
        raise ValueError('Construction repair failed: '+str(job['error']))
    payload = json.loads(execution['payload'])
    payload['repair_of_execution_job']=execution_job
    payload['repair_case_sha256']=digest(request['case'])
    payload['preserved_target_comparisons']=comparisons or payload.get('preserved_target_comparisons',[])
    payload['repair_number']=payload.get('repair_number',0)+1
    with store.transaction():
        replacement = stages.enqueue(store,run_id,'execution',execution['entity'],execution['actor'],payload,[construction])
    from .construction_reuse import refresh_pending
    refresh_pending(store,run_id,construction)
    return replacement


def repair_until_accepted(initial, inspect, reconstruct, *, max_repairs=2):
    """Bounded repairs, retaining evidence; caller continues independent cases."""
    if max_repairs<0:
        raise ValueError('Repair limit cannot be negative')
    current=initial;history=[]
    for number in range(max_repairs+1):
        try:
            result=inspect(current)
        except Exception as exc:
            result={'status':'failed','error':str(exc)}
        if result.get('status')=='validated':
            result['repair_history']=history
            return result
        history.append({k:result[k] for k in ('execution','error','status') if k in result})
        if number==max_repairs:
            break
        try:
            current=reconstruct(current,result)
        except Exception as exc:
            result['repair_error']=str(exc)
            break
    result.update(status='needs_repair',repair_history=history)
    return result


def execute_with_repairs(store, run_id, python, host='127.0.0.1', port=20000, timeout=600, *, max_repairs=2, engines=None, semantic_limiter=None, job_ids=()):
    """Repair physical/capture failures; full scenario labeling follows adaptation."""
    from .engines import execute_pool
    engines=engines if engines is not None else [{'id':'single','python':python,'host':host,'port':port}]
    job_ids=tuple(job_ids)
    execute_pool(store,run_id,engines,timeout=timeout,job_ids=job_ids)
    job_filter=(' AND j.id IN ('+','.join('?' for _ in job_ids)+')') if job_ids else ''
    jobs=store.db.execute("SELECT j.id FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? AND r.active=1 AND j.stage='execution' AND j.status IN ('pending','failed','completed')"+job_filter+" ORDER BY j.id",(run_id,*job_ids)).fetchall()
    accepted=0
    def inspect(ident):
        job=store.job(ident)
        if job['status']=='pending':
            execute_pool(store,run_id,engines,timeout=timeout,job_ids=(ident,))
            job=store.job(ident)
        if job['status']=='completed':
            result=store.artifact(job['artifact_id'])['payload']
            from recording_store import stored_attempt_path
            return {'status':'validated' if not result['rebuild_required'] else 'failed',
                    'execution':str(stored_attempt_path(store,ident,job['attempts'])),'error':'Recorded setup, target, or maneuver requires repair' if result['rebuild_required'] else None}
        request=json.loads(job['payload'])
        from recording_store import attempt_path
        directory=attempt_path(run_id,ident,job['attempts'])
        return {'status':'failed','execution':str(directory),'error':job['error'] or 'Execution is not complete'}
    for row in jobs:
        if not store.db.execute('SELECT 1 FROM run_jobs WHERE run_id=? AND job_id=? AND active=1',(run_id,row['id'])).fetchone():
            continue
        latest=[row['id']]
        def reconstruct(ident,failure):
            path=Path(failure['execution'])/'failure.json'
            if path.is_file() and json.loads(path.read_text()).get('engine_unavailable'):
                raise ValueError('Transport/termination is uncertain; recover the original attempt before diagnosing construction repairs')
            new=schedule_repair(store,run_id,ident,failure,timeout=timeout,limiter=semantic_limiter);latest[0]=new;return new
        used=json.loads(store.job(row['id'])['payload']).get('repair_number',0)
        result=repair_until_accepted(row['id'],inspect,reconstruct,max_repairs=max(0,max_repairs-used))
        if result['status']=='validated':
            accepted+=1
        else:
            store.db.execute("UPDATE jobs SET status='failed',error=? WHERE id=? AND status!='running'",
                             (result.get('repair_error') or result.get('error') or 'Diagnosed repair still required',latest[0]))
    return accepted
