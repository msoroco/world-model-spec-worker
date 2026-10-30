"""Bounded execution pool. Only this coordinator touches SQLite."""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
import uuid

from . import stages
from .completion import atomic_result, verify, seal
from .engine_worker import identity_key
from .store import atomic, digest

WORKER = Path(__file__).with_name('engine_worker.py').resolve()


def command(engine, args):
    argv = [engine['python'], str(WORKER)] + list(args)
    remote = engine.get('ssh')
    if remote:
        if remote.startswith('-') or any(c.isspace() for c in remote):
            raise ValueError('Invalid SSH hostname')
        return ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                '-o', 'ConnectTimeout=10', remote, shlex.join(argv)]
    return argv


def preflight(engine):
    args = ['--probe', str(engine['port'])]
    if engine.get('allow_login_node', False):
        args.append('--allow-login-node')
    value = json.loads(subprocess.check_output(command(engine, args),
                                              text=True, timeout=30))
    if engine['host'] not in ('localhost', '127.0.0.1', '::1', value['server_identity']['node']):
        raise ValueError('Controller/capture must run on the CARLA server node; use its local endpoint')
    return value


def dispatch(engine, request_file, timeout):
    directory = request_file.parent
    with (directory / 'worker.stdout.log').open('w') as out, (directory / 'worker.stderr.log').open('w') as err:
        process = subprocess.Popen(command(engine, ['--request', str(request_file)]), stdout=out, stderr=err)
        try:
            code = process.wait(timeout=2 * timeout + 30)
        except BaseException:
            # SSH termination does not prove the remote driving process stopped.
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
            raise
    if code:
        raise RuntimeError('Execution worker failed; retained logs: ' + str(directory))


def normalize(engines):
    if not isinstance(engines, list) or not engines:
        raise ValueError('Engines must be a nonempty JSON array')
    ids = set(); result = []
    for raw in engines:
        item = dict(raw)
        if not isinstance(item.get('id'), str) or not item['id'] or item['id'] in ids:
            raise ValueError('Engine IDs must be nonempty and unique')
        ids.add(item['id'])
        if not isinstance(item.get('python'), str) or not Path(item['python']).is_absolute():
            raise ValueError('Each engine needs an absolute Python interpreter path')
        if not isinstance(item.get('allow_login_node', False), bool):
            raise ValueError('allow_login_node must be an explicit boolean')
        item.setdefault('host', '127.0.0.1'); item.setdefault('port', 20000)
        if not isinstance(item['port'], int) or not 1 <= item['port'] <= 65535:
            raise ValueError('Invalid CARLA port')
        if item.get('scratch_fallback'):
            fallback=item['scratch_fallback']
            if not isinstance(fallback,dict) or not fallback.get('diagnosis') or not Path(fallback.get('root','')).is_absolute():
                raise ValueError('Scratch fallback requires an absolute task-owned root and explicit I/O diagnosis')
        result.append(item)
    return result


def prepare(store, run, job, engine, snapshot, hashes):
    request = json.loads(job['payload'])
    from recording_store import begin_recording
    directory = begin_recording(run, job['id'], job['attempts'], request['cell']['cell_id'], job['actor'], request['case']['case_id'])
    inputs, provenance = stages.input_context(store, run, job)
    construction = next(d for d in inputs['dependencies'] if 'files' in d)
    for f in construction['files']:
        target = (directory / f['path']).resolve()
        if directory.resolve() not in target.parents:
            raise ValueError('Construction file escapes attempt')
        target.parent.mkdir(parents=True, exist_ok=True); target.write_text(f['content'])
    atomic(directory / 'construction.json', construction)
    parent = store.db.execute('SELECT j.* FROM dependencies d JOIN jobs j ON j.id=d.dependency_id WHERE d.job_id=? AND j.stage="construction"', (job['id'],)).fetchone()
    if json.loads(parent['payload']).get('template_ids'):
        context, _ = stages.input_context(store, run, dict(parent))
        atoms = context['simulator_context']['capture_requirements']['required_atoms']
    else:
        from .construction_contract import required_capture_atoms
        atoms = required_capture_atoms({}, [], request['case'])
    atomic(directory / 'capture_requirements.json', {'required_atoms': atoms})
    project = Path(__file__).resolve().parents[2]
    env = {'PYTHONPATH': os.pathsep.join(str(p) for p in (project/'scripts', project/'third_party/carla_scene_graphs', project/'carla/PythonAPI/carla')),
           'SCENARIO_REQUIRED_CAPTURE_ATOMS': json.dumps(atoms), 'PYTHONNOUSERSITE': '1', 'MPLBACKEND': 'Agg'}
    binding = {'run_id': run, 'job_id': job['id'], 'attempt_number': job['attempts'],
               'cell_id': request['cell']['cell_id'], 'actor': job['actor'], 'case_id': request['case']['case_id'],
               'specification_hash': digest(request['case']), 'configuration_hash': digest(construction),
               'implementation_hash': digest([f for f in construction['files'] if f['path'].endswith('.py')]),
               'runtime_dependency_hashes': hashes, 'server_identity': snapshot['server_identity']}
    from pipeline_paths import OUTPUT_ROOT
    worker_request = {'directory': str(directory), 'binding': binding, 'entrypoint': construction['entrypoint'],
                      'env': env, 'host': engine['host'], 'port': engine['port'],
                      'lock_directory': str(OUTPUT_ROOT / 'state/engines'),
                      'scratch_fallback':engine.get('scratch_fallback')}
    metadata = {'directory': str(directory), 'binding': binding, 'engine': engine, 'resource_snapshot': snapshot,
                'runtime_dependency_hashes': hashes}
    store.db.execute('UPDATE attempts SET metadata=? WHERE job_id=? AND number=?',
                     (json.dumps(metadata), job['id'], job['attempts']))
    return worker_request, metadata, request, construction, provenance


def validate_saved(directory, binding, request, construction, metadata):
    from .carla import validate_attempt
    result = verify(directory, binding)
    metadata['recorded_exit_code'] = result.get('recorded_exit_code', 0)
    result = validate_attempt(Path(directory), request, construction, metadata, binding['runtime_dependency_hashes'])
    atomic_result(Path(directory) / 'result.json', result)
    return seal(directory, binding)


def drive(engine, worker_request, metadata, request, construction, timeout, static_timeout=None):
    worker_request['timeout'] = timeout
    worker_request['static_timeout'] = static_timeout if static_timeout is not None else timeout
    metadata['runtime_budget']={'recorded_wall_seconds':timeout,'static_wall_seconds':worker_request['static_timeout']}
    path = Path(worker_request['directory']) / 'worker_request.json'
    atomic(path, worker_request)
    dispatch(engine, path, timeout)
    return validate_saved(path.parent, worker_request['binding'], request, construction, metadata)


def recover(store, run, owner, *, job_ids=()):
    """Adopt only expired/interrupted attempts with independently verified evidence."""
    count = 0
    filters = " AND j.id IN ("+",".join("?" for _ in job_ids)+")" if job_ids else ""
    rows = store.db.execute("SELECT j.*,a.metadata FROM jobs j JOIN run_jobs r ON r.job_id=j.id JOIN attempts a ON a.job_id=j.id AND a.number=j.attempts WHERE r.run_id=? AND r.active=1 AND j.stage='execution' AND (j.status='failed' OR (j.status='running' AND j.lease_until<?))"+filters, (run, time.time(), *job_ids)).fetchall()
    for row in rows:
        metadata = json.loads(row['metadata'] or '{}')
        directory = Path(metadata.get('directory', '/nonexistent'))
        if not metadata.get('binding') or not (directory / 'result.json').is_file():
            continue
        try:
            request = json.loads(row['payload'])
            binding = metadata['binding']
            if binding['specification_hash'] != digest(request['case']):
                raise ValueError('Frozen case changed before recovery')
            construction = json.loads((directory / 'construction.json').read_text())
            if binding['configuration_hash'] != digest(construction):
                raise ValueError('Construction changed before recovery')
            result = validate_saved(directory, binding, request, construction, metadata)
            _, provenance = stages.input_context(store, run, dict(row))
            with store.transaction():
                changed = store.db.execute("UPDATE jobs SET owner=?,status='running',lease_until=? WHERE id=? AND (status='failed' OR (status='running' AND lease_until<?))", (owner, time.time()+180, row['id'], time.time())).rowcount
                if not changed:
                    continue
            metadata['recovered_without_driving'] = True
            store.finish(store.job(row['id']), owner, result, provenance, metadata)
            count += 1
        except Exception as exc:
            store.db.execute("UPDATE jobs SET error=? WHERE id=? AND status='failed'", ('Recovery rejected: '+str(exc), row['id']))
    return count


def execute_pool(store, run, engines, *, timeout=600, job_ids=()):
    from .runtime_dependencies import execution_guard
    if timeout < 1:
        raise ValueError('Execution timeout must be positive')
    engines = normalize(engines)
    owner = uuid.uuid4().hex
    with execution_guard(store, run, job_ids=job_ids) as hashes:
        count = recover(store, run, owner, job_ids=job_ids)
        filters = ' AND j.id IN ('+','.join('?' for _ in job_ids)+')' if job_ids else ''
        pending = store.db.execute("SELECT COUNT(*) FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? AND r.active=1 AND j.stage='execution' AND j.status='pending'"+filters, (run, *job_ids)).fetchone()[0]
        if not pending:
            return count
        base_timeout=timeout
        # Model authoring and static checks retain the configured deadline.
        # Recorded physics can require more wall time than simulated time.
        constructions=store.db.execute("SELECT a.payload FROM jobs j JOIN run_jobs r ON r.job_id=j.id JOIN dependencies d ON d.job_id=j.id JOIN jobs p ON p.id=d.dependency_id JOIN artifacts a ON a.id=p.artifact_id WHERE r.run_id=? AND r.active=1 AND j.stage='execution' AND j.status='pending' AND p.stage='construction' AND p.status='completed'"+filters,(run,*job_ids)).fetchall()
        for construction_row in constructions:
            rules=json.loads(construction_row['payload']).get('termination_rules',{})
            limits=rules.get('limits',{}) if isinstance(rules,dict) else {}
            seconds=limits.get('maximum_simulation_seconds')
            if isinstance(seconds,(int,float)) and not isinstance(seconds,bool) and 0<seconds<1000000:
                timeout=max(timeout,min(3600,int(seconds*3+0.999999)))
        ready=[]; snapshots=[]; rejected=[]
        for engine in engines:
            try:
                snapshots.append(preflight(engine)); ready.append(engine)
            except Exception as exc:
                rejected.append({'engine': engine['id'], 'error': str(exc)})
        if rejected:
            atomic(Path(stages.run_info(store,run)['output'])/'logs/engine_preflight.json', rejected)
        engines=ready
        if not engines:
            raise RuntimeError('No reachable, identifiable CARLA engines; see logs/engine_preflight.json')
        keys = ['carla-process:'+identity_key(s['server_identity']) for s in snapshots]
        if len(keys) != len(set(keys)):
            raise ValueError('Multiple workers reach the same actual CARLA server')
        leased = []
        try:
            lease_deadline=time.monotonic()+2*timeout+120
            while not leased:
                busy=False
                with store.transaction():
                    for key in keys:
                        row = store.db.execute('SELECT * FROM resource_leases WHERE resource=?', (key,)).fetchone()
                        if row and row['expires'] > time.time():
                            busy=busy or row['owner']!='unavailable'
                            continue
                        store.db.execute('INSERT OR REPLACE INTO resource_leases VALUES(?,?,?)', (key, owner, time.time()+2*timeout+120))
                        leased.append(key)
                        # Reserve only the capacity this ready set can use.
                        if len(leased)>=pending:
                            break
                if not leased:
                    if not busy or time.monotonic()>=lease_deadline:
                        raise RuntimeError('Every CARLA server is owned or unavailable; confirm readiness or restart an uncertain server')
                    time.sleep(1)
            with ThreadPoolExecutor(max_workers=len(engines)) as pool:
                active = {}; free = [i for i, key in enumerate(keys) if key in leased]; heartbeat = 0
                while free or active:
                    for index in list(free):
                        job = store.claim(run, owner, ('execution',), 2*timeout+120, job_ids=job_ids)
                        if not job:
                            free.remove(index); continue
                        free.remove(index)
                        try:
                            data = prepare(store, run, job, engines[index], snapshots[index], hashes)
                            worker_request, metadata, request, construction, provenance = data
                            future = pool.submit(drive, engines[index], worker_request, metadata, request, construction, timeout, base_timeout)
                            active[future] = (index, job, metadata, provenance)
                        except Exception as exc:
                            store.fail(job, owner, exc)
                            free.append(index)
                    if not active:
                        continue
                    done, _ = wait(active, timeout=.2, return_when=FIRST_COMPLETED)
                    if time.monotonic()-heartbeat > 20:
                        for _, job, _, _ in active.values():
                            store.heartbeat(job['id'], owner, 2*timeout+120)
                        for key in leased:
                            store.db.execute('UPDATE resource_leases SET expires=? WHERE resource=? AND owner=?', (time.time()+2*timeout+120, key, owner))
                        heartbeat = time.monotonic()
                    for future in done:
                        index, job, metadata, provenance = active.pop(future)
                        try:
                            result = future.result()
                            from recording_store import finish_phase
                            finish_phase(metadata['directory'], 'recorded')
                            store.finish(job, owner, result, provenance, metadata)
                            count += 1
                            free.append(index)
                        except Exception as exc:
                            directory = Path(metadata['directory'])
                            failure_path = directory / 'failure.json'
                            failure = json.loads(failure_path.read_text()) if failure_path.exists() else {'engine_unavailable': not (directory/'result.json').exists()}
                            from recording_store import finish_phase
                            finish_phase(directory, 'failed')
                            failure.update(error=str(exc), metadata=metadata, unconfirmed=True)
                            atomic(failure_path, failure)
                            store.fail(job, owner, exc, metadata=metadata)
                            if failure.get('engine_unavailable'):
                                store.db.execute('UPDATE resource_leases SET owner=?,expires=? WHERE resource=?', ('unavailable', 1e30, keys[index]))
                            else:
                                free.append(index)
        finally:
            for key in leased:
                store.db.execute('DELETE FROM resource_leases WHERE resource=? AND owner=?', (key, owner))
        return count
