"""Optional local-only stage adoption. Never included in worker repositories."""
import json
import shutil
from pathlib import Path
from .common import digest, read, sha, within, write
from .exchange import check_return, import_return


def adopt(root, repo, batch_id, db, run, plan_file):
    """Adopt ONE reviewed proposal into an explicit pending semantic job.

    The local plan is not supplied by the worker. It specifies assignment_id,
    proposal, job_id, and expected_cache_key. The job must already have a fresh
    frozen input_revision matching imported code's package hash. Creating that
    revision is supported by freeze(); normal stage preparation creates jobs.
    """
    from batch_pipeline import stages
    from batch_pipeline.store import Store
    plan = read(plan_file)
    imported = import_return(root, repo, batch_id)
    aid = plan['assignment_id']
    if aid not in imported['destinations'] or imported['results'][aid]['status'] not in ('prepared', 'ready'):
        raise ValueError('Only a prepared, imported assignment can be adopted')
    proposal_path = within(Path(repo) / 'work' / aid, plan['proposal'])
    proposal = read(proposal_path)
    assignment = read(Path(repo) / 'inputs' / aid / 'assignment.json')
    if Path(db).resolve().parent != Path(root).resolve() / 'state':
        raise ValueError('Database must belong to the specified artifact root')
    store = Store(db)
    try:
        # Store.claim recovery is global; require an idle database before calling it.
        if store.db.execute("SELECT 1 FROM jobs WHERE status='running' LIMIT 1").fetchone() or store.db.execute('SELECT 1 FROM resource_leases LIMIT 1').fetchone():
            raise ValueError('Stage adoption requires idle local jobs/resources')
        job = store.job(plan['job_id'])
        if not job or job['stage'] not in stages.SKILLS or job['cache_key'] != plan['expected_cache_key']:
            raise ValueError('Wrong job identity or stage')
        if not store.db.execute('SELECT 1 FROM run_jobs WHERE run_id=? AND job_id=? AND active=1', (run, job['id'])).fetchone():
            raise ValueError('Job is not active in the specified run')
        request = json.loads(job['payload'])
        revision = request.get('input_revision')
        if not revision:
            raise ValueError('Prepare a fresh frozen revision before adoption')
        from batch_pipeline.run_inputs import job_revision
        frozen = job_revision(store, run, revision)
        if frozen['provenance'].get('worker_exchange_package') != imported['package_sha256']:
            raise ValueError('Job revision is not frozen against this returned code package')
        if job['actor'] != assignment['actor']:
            raise ValueError('Wrong actor')
        if request.get('cell', {}).get('cell_id', assignment['cell_id']) != assignment['cell_id']:
            raise ValueError('Wrong cell')
        if request.get('law_id', assignment['law_id']) != assignment['law_id']:
            raise ValueError('Wrong law')
        from law_split import assignment_allowed
        if not assignment_allowed(assignment['law_id'], assignment['cell_id'], assignment['actor'], assignment['role'], root):
            raise ValueError('Assignment no longer eligible')
        if job['stage'] == 'cases' and any(c.get('target_law_id') not in (None, assignment['law_id']) for c in [*proposal.get('cases', []), *proposal.get('sweep_specs', [])]):
            raise ValueError('Proposal adds an unassigned law')
        if job['stage'] == 'construction' and request.get('case', {}).get('target_law_id') != assignment['law_id']:
            raise ValueError('Construction targets another law')
        inputs, provenance = stages.input_context(store, run, job)
        stages.validate(job['stage'], proposal, inputs)
        provenance.update(worker_exchange_package=imported['package_sha256'],
                          worker_exchange_commit=imported['return_git']['commit'],
                          worker_proposal_sha256=sha(proposal_path))
        if job['status'] == 'completed':
            artifact = store.artifact(job['artifact_id'])
            if artifact['payload'] != proposal or artifact['provenance'].get('worker_proposal_sha256') != sha(proposal_path):
                raise ValueError('Completed job differs; no overwrite')
            return {'job_id': job['id'], 'artifact_id': job['artifact_id'], 'already_adopted': True}
        if job['status'] != 'pending':
            raise ValueError('Adoption does not recover/retry failed or interrupted jobs')
        owner = 'worker-exchange-' + digest(plan)[:16]
        claimed = store.claim(run, owner, [job['stage']], job_ids=[job['id']])
        if not claimed:
            raise ValueError('Exact job not ready; dependencies must complete first')
        try:
            artifact_id = store.finish(claimed, owner, proposal, provenance,
                                       {'worker_exchange': imported['package_sha256']},
                                       expand=lambda ident: stages.expand(store, run, claimed, proposal, ident))
        except Exception as exc:
            store.fail(claimed, owner, str(exc))
            raise
        return {'job_id': job['id'], 'artifact_id': artifact_id, 'input_revision': revision,
                'recording_accepted': False, 'simulation_dispatched': False}
    finally:
        store.db.close()


def freeze(root, repo, batch_id, db, run, base_revision, config_file):
    """Freeze a child only; never select cases or dispatch jobs."""
    from batch_pipeline.store import Store
    from batch_pipeline.run_inputs import freeze_job_revision, job_revision
    imported = import_return(root, repo, batch_id)
    if Path(db).resolve().parent != Path(root).resolve() / 'state':
        raise ValueError('Database must belong to the specified artifact root')
    store = Store(db)
    try:
        if store.db.execute("SELECT 1 FROM jobs WHERE status='running' LIMIT 1").fetchone() or store.db.execute('SELECT 1 FROM resource_leases LIMIT 1').fetchone():
            raise ValueError('Freeze requires idle local state')
        base = job_revision(store, run, base_revision)
        config = read(config_file)
        if config.get('judgment_policy') != 'fixed_sweeps':
            raise ValueError('Provide a complete reviewed fixed_sweeps config; do not inherit wrong-law context')
        assignments = [read(Path(repo) / 'inputs' / aid / 'assignment.json') for aid in imported['destinations']]
        required_laws = {a['law_id'] for a in assignments}
        if set(config.get('law_scope', {}).get('records', {})) != required_laws:
            raise ValueError('Local config law_scope must match the imported assignments exactly')
        if any(law not in config.get('summaries', {}) for law in required_laws):
            raise ValueError('Missing exact local law summaries')
        frozen_locations = {}
        from .common import tree
        for aid, source in imported['destinations'].items():
            target = Path(root) / 'inputs/worker_exchange' / batch_id / 'implementations' / imported['package_sha256'] / aid
            if target.exists():
                if tree(target) != tree(source):
                    raise ValueError('Frozen implementation changed')
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source, target)
            frozen_locations[aid] = str(target)
        bundle_root = Path(root) / 'inputs/worker_exchange' / batch_id / 'implementations' / imported['package_sha256']
        for directory in ('runtime', 'inputs'):
            source, target = Path(repo) / directory, bundle_root / directory
            if target.exists():
                if tree(target) != tree(source):
                    raise ValueError('Frozen runtime/input dependencies changed')
            else:
                shutil.copytree(source, target)
        config = dict(config, worker_exchange={
            'package_sha256': imported['package_sha256'], 'code_locations': frozen_locations,
            'return_commit': imported['return_git']['commit'], 'runtime_location': str(bundle_root / 'runtime'),
            'input_location': str(bundle_root / 'inputs')})
        from batch_pipeline.runtime_dependencies import discover, snapshot
        dependency_paths = discover(config.get('simulator_context'))
        dependency_paths += [p for p in bundle_root.rglob('*') if p.is_file()]
        # New helper code is explicit even though historical discovery predates it.
        dependency_paths += list(Path(__file__).resolve().parent.glob('*.py'))
        config['runtime_dependencies'] = snapshot(dependency_paths)
        catalog = dict(base['catalog'], law_records=dict(base['catalog']['law_records']))
        for assignment in assignments:
            law = assignment.get('law_record', assignment.get('law'))
            if law is not None:
                catalog['law_records'][assignment['law_id']] = law
        revision = freeze_job_revision(store, run, catalog, config,
            {'parent_revision': base_revision, 'worker_exchange_package': imported['package_sha256'],
             'return_commit': imported['return_git']['commit'], 'reason': 'fresh worker implementation child'})
        receipt = {'run': run, 'input_revision': revision, 'parent_revision': base_revision,
                   'package_sha256': imported['package_sha256'], 'status': 'frozen_not_dispatched'}
        write(Path(root) / 'inputs/worker_exchange' / batch_id / ('revision-' + revision + '.json'), receipt)
        return receipt
    finally:
        store.db.close()


def adopt_manifest_case(root,repo,batch_id,db,run,assignment_id,case_id,job_id,expected_cache_key):
    """Translate an explicit manifest selection into the existing supported adopter."""
    from .execution_manifest import validate
    from .exchange import check_return
    check_return(root,repo,batch_id)
    manifest=validate(repo,assignment_id)
    entry=next((e for e in manifest['cases'] if e['case_id']==case_id),None)
    if entry is None:raise ValueError('Case not in manifest')
    # User-selected case and job only: no queue scan, recovery, or dispatch.
    plan={'assignment_id':assignment_id,'proposal':entry['construction'],'job_id':job_id,'expected_cache_key':expected_cache_key}
    path=Path(root)/'state/operations/worker_exchange'/batch_id/'stage-plans'/(str(job_id)+'.json')
    write(path,plan)
    result=adopt(root,repo,batch_id,db,run,path)
    result['recording_role']='research' if entry['kind']=='capability' else 'delivery_candidate'
    result['automatic_recording_acceptance']=False
    return result


def prepare_manifest_jobs(root,repo,batch_id,db,run,assignment_id,cases_job_id,case_ids):
    """Select and adopt exact manifest cases after canonical semantic-stage adoption.

    No semantic labels or bindings are guessed. The caller supplies the completed
    canonical cases-stage job; worker proposals have already been validated and
    adopted through ordinary stages. Never dispatches a simulation.
    """
    from .execution_manifest import validate
    from .exchange import check_return
    from batch_pipeline.store import Store
    import pipeline
    check_return(root,repo,batch_id);manifest=validate(repo,assignment_id)
    selected=set(case_ids)
    if not selected or not selected <= {c['case_id'] for c in manifest['cases']}:
        raise ValueError('Select explicit manifest cases')
    if Path(db).resolve().parent != Path(root).resolve()/'state':raise ValueError('Wrong artifact database')
    store=Store(db)
    try:
        if store.db.execute("SELECT 1 FROM jobs WHERE status='running' LIMIT 1").fetchone() or store.db.execute('SELECT 1 FROM resource_leases LIMIT 1').fetchone():
            raise ValueError('Prepare jobs while local pipeline is idle')
        parent=store.job(cases_job_id)
        if not parent or parent['stage']!='cases' or parent['status']!='completed':raise ValueError('Completed canonical cases job required')
        if not store.db.execute('SELECT 1 FROM run_jobs WHERE run_id=? AND job_id=? AND active=1',(run,cases_job_id)).fetchone():raise ValueError('Cases job is not active in run')
        payload=json.loads(parent['payload']);revision=payload.get('input_revision')
        prepared=store.artifact(parent['artifact_id'])['payload'];known={c['case_id']:c for c in prepared['cases']}
        if not selected <= known.keys() or any(known[c]['target_type']=='baseline' for c in selected):raise ValueError('Undefined or baseline selection')
        pipeline.choose_simulation(store,run,cell_ids=[parent['entity']],actor_ids=[parent['actor']],case_ids=sorted(selected))
        jobs=[]
        for row in store.db.execute("SELECT j.* FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? AND r.active=1 AND j.stage='construction' AND j.actor=?",(run,parent['actor'])):
            request=json.loads(row['payload'])
            if request.get('case',{}).get('case_id') in selected and request.get('input_revision')==revision:
                jobs.append(dict(row))
        if len(jobs)!=len(selected):raise ValueError('Exact selected construction identity ambiguous')
    finally:store.db.close()
    results=[]
    for job in jobs:
        case=json.loads(job['payload'])['case']['case_id']
        results.append(adopt_manifest_case(root,repo,batch_id,db,run,assignment_id,case,job['id'],job['cache_key']))
    store=Store(db)
    try:
        executions=[]
        for row in store.db.execute("SELECT j.id,j.payload FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? AND r.active=1 AND j.stage='execution'",(run,)):
            request=json.loads(row['payload'])
            if request.get('case',{}).get('case_id') in selected and request.get('input_revision')==revision:executions.append(row['id'])
    finally:store.db.close()
    return {'native_revision':revision,'exact_execution_job_ids':executions,'construction_adoption':results,'simulation_dispatched':False}
