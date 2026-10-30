"""One live implementation, coordinated edits, and hash-bound run provenance."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import time

from .store import atomic, encode


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def discover(resources=None):
    root = Path(__file__).resolve().parents[1]
    project = Path((resources or {}).get('project_root', root.parent))
    paths = list((root/'batch_pipeline').glob('*.py')) + list((root/'traffic_spec_adapter').glob('*.py'))
    paths += [root/name for name in ('pipeline.py','pipeline_paths.py','workspaces.py','law_split.py','recording_store.py','run_selected.py','control_evidence.py',
              'review_recordings.py','expected_labels.py','authored_context.py','intentions.py','trace_json.py','trace_derivations.py','trace_scope_audit.py',
              'speed_overlay.py','scenario_overlay.py','demo_rule_evidence.py','production_verdicts.py','production_metadata.py')]
    paths += [project/'scripts'/name for name in ('pipeline_capture.py','scene_graph_collector.py','original_observations.py')]
    paths += [project/'third_party/carla_scene_graphs/carla_sgg'/name for name in ('sgg.py','sgg_abstractor.py','actors.py','utils.py','law_evidence.py')]
    required = [Path(p) for p in (resources or {}).get('runtime_dependency_paths',[])]
    capture = (resources or {}).get('capture_requirements',{})
    for key in ('helper_path','helper'):
        if capture.get(key):
            required.append(Path(capture[key]))
    for path in required:
        if not path.is_file():
            raise ValueError('Missing configured runtime dependency: '+str(path))
    return sorted({p.resolve() for p in paths if p.is_file()} | {p.resolve() for p in required})


def snapshot(paths):
    return {str(Path(p).resolve()): sha(p) for p in paths}


def lock_path():
    from pipeline_paths import OUTPUT_ROOT
    return OUTPUT_ROOT/'state/runtime-edit.lock'


@contextmanager
def coordinated_access(*, editing=False, path=None):
    path = Path(path) if path else lock_path()
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX if editing else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(stream,fcntl.LOCK_UN)


def assert_current(expected):
    changed = [p for p,value in expected.items() if not Path(p).is_file() or sha(p)!=value]
    if changed:
        raise ValueError('Runtime dependencies changed; diagnose and use runtime-edit to record the intentional repair: '+', '.join(changed))


def persist(store, run_id, config):
    store.db.execute('UPDATE runs SET config=? WHERE id=?',(encode(config),run_id))
    getattr(store,'_run_cache',{}).pop(run_id,None)
    row = store.db.execute('SELECT output FROM runs WHERE id=?',(run_id,)).fetchone()
    atomic(Path(row[0])/'runtime_dependencies.json',config['runtime_dependencies'])


@contextmanager
def execution_guard(store, run_id, *, job_ids=()):
    """Pin explicitly selected continuation jobs to their immutable runtime.

    Historical run configuration is left untouched for revision-bound jobs.
    A single pool cannot silently mix revisions or select another run's job.
    """
    from .stages import run_info
    with coordinated_access():
        expected = None
        revision = None
        if job_ids:
            selected = tuple(dict.fromkeys(job_ids))
            marks = ','.join('?' for _ in selected)
            rows = store.db.execute(
                "SELECT j.id,j.payload FROM jobs j JOIN run_jobs r ON r.job_id=j.id "
                "WHERE r.run_id=? AND r.active=1 AND j.stage='execution' "
                "AND j.id IN ("+marks+")", (run_id, *selected)).fetchall()
            if {row['id'] for row in rows} != set(selected):
                raise ValueError('Selected execution jobs do not belong to the active run')
            revisions = {json.loads(row['payload']).get('input_revision') for row in rows}
            if len(revisions) != 1:
                raise ValueError('Execution pool cannot mix immutable input revisions')
            revision = next(iter(revisions))
            if revision is not None:
                from .run_inputs import job_revision
                expected = job_revision(store, run_id, revision)['config'].get('runtime_dependencies')
                if not expected:
                    raise ValueError('Selected input revision has no frozen runtime dependencies')
        if revision is None:
            info = run_info(store, run_id)
            expected = info['config'].get('runtime_dependencies')
            if expected is None:
                config = dict(info['config'])
                expected = snapshot(discover(config.get('simulator_context')))
                config['runtime_dependencies'] = expected
                persist(store, run_id, config)
        assert_current(expected)
        yield expected
        assert_current(expected)


def refresh(store, run_id, reason, case_ids=()):
    """Caller holds the exclusive edit lock; preserve attempts and requeue cases."""
    from .stages import run_info
    if not reason.strip():
        raise ValueError('An intentional dependency repair needs a reason')
    info = run_info(store,run_id);config = dict(info['config'])
    old = config.get('runtime_dependencies',{})
    new = snapshot(discover(config.get('simulator_context')))
    changed = sorted(p for p in set(old)|set(new) if old.get(p)!=new.get(p))
    if not changed:
        return []
    jobs = store.db.execute("SELECT j.* FROM jobs j JOIN run_jobs r ON r.job_id=j.id WHERE r.run_id=? AND r.active=1 AND j.stage='execution'",(run_id,)).fetchall()
    known={json.loads(j['payload'])['case']['case_id'] for j in jobs}
    if set(case_ids)-known:
        raise ValueError('Unknown affected case IDs: '+', '.join(sorted(set(case_ids)-known)))
    affected = [j for j in jobs if not case_ids or json.loads(j['payload'])['case']['case_id'] in case_ids]
    if any(j['status']=='running' for j in jobs):
        raise ValueError('An active execution must finish before recording a dependency repair')
    with store.transaction():
        config['runtime_dependencies']=new
        capture=(config.get('simulator_context') or {}).get('capture_requirements',{})
        helper=capture.get('helper_path') or capture.get('helper') or str(Path((config.get('simulator_context') or {}).get('project_root',Path(__file__).resolve().parents[2]))/'scripts/pipeline_capture.py')
        if helper in new and 'helper_source' in capture:
            capture['helper_source']=Path(helper).read_text()
        persist(store,run_id,config)
        for j in affected:
            store.db.execute("UPDATE jobs SET status='pending',available=0,error=NULL,owner=NULL,lease_until=NULL WHERE id=?",(j['id'],))
        store.db.execute('INSERT INTO events(job_id,created,message) VALUES(NULL,?,?)',
                         (time.time(),encode({'runtime_repair':reason,'changed_paths':changed,'previous_hashes':old,'current_hashes':new,'affected_execution_jobs':[j['id'] for j in affected]})))
    index=Path(info['output'])/'delivery_index.json'
    if index.exists():
        data=json.loads(index.read_text());ids={json.loads(j['payload'])['case']['case_id'] for j in affected}
        for cell in data['cells']:
            for case in cell['cases']:
                if case['case_id'] in ids:
                    case.update(status='needs_repair',expected_label_status='needs_repair',dependency_repair_reason=reason)
            if any(c['case_id'] in ids for c in cell['cases']):cell['status']='pending'
        data['status']='repairs_in_progress';atomic(index,data)
    return [j['id'] for j in affected]
