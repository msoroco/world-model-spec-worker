"""Local batch construction and immutable return import. No worker code executes."""
import json
import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from .common import SETS, SKILLS, assignment_id, digest, name, read, sha, tree, within, write
from .portable import check, inspect_file

MODULE = Path(__file__).resolve().parent


def scope_path(root, set_id):
    if set_id not in SETS:
        raise ValueError('Unknown active set: ' + set_id)
    return Path(root) / 'sets' / set_id / 'scope.json'


def role(set_id):
    return {'demo-train': 'training', 'full-train': 'training',
            'demo-test': 'testing', 'full-test': 'testing', 'held-out': 'heldout'}[set_id]


def groups(root, set_id):
    values = {}
    for row in read(scope_path(root, set_id))['assignments']:
        aid = assignment_id(row, role(set_id))
        values.setdefault(aid, []).append(row)
    return values


def partition(root, set_id, count, destination, selected=None):
    """Explicitly partition the requested scope; never infer the user's next work."""
    if count < 1:
        raise ValueError('Partition count must be positive')
    available = groups(root, set_id)
    ids = sorted(selected if selected is not None else available)
    if not ids or len(set(ids)) != len(ids) or set(ids) - available.keys():
        raise ValueError('Empty/duplicate/unknown assignment selection')
    if count > len(ids):
        raise ValueError('More partitions than assignments')
    dest = Path(destination)
    if dest.exists():
        raise ValueError('Partition destination already exists')
    dest.mkdir(parents=True)
    for n in range(count):
        write(dest / f'{set_id}-{n+1:02d}.json', {
            'format': 'worker-partition-v1', 'partition_id': f'{set_id}-{n+1:02d}',
            'set_id': set_id, 'scope_sha256': sha(scope_path(root, set_id)),
            'assignment_ids': ids[n::count]})
    return [str(p) for p in sorted(dest.glob('*.json'))]


def workspace(root, a, set_ids):
    # Read-only review/context locator. Never use this as an implementation target.
    from workspaces import law_directory, work_index
    if work_index(root).get('format') == 'set-review-workspaces-v2':
        set_id = {'training':'full-train', 'testing':'full-test', 'heldout':'held-out'}[a['role']]
        return law_directory(a['cell_id'], a['law_id'], set_id=set_id, root=root)
    key = '|'.join((a['cell_id'], a['law_id'], a['actor']))
    category = work_index(root).get('assignments', {}).get(key, {}).get('category')
    if not category:
        demo_set = 'demo-train' if a['role'] == 'training' else 'demo-test'
        demo = Path(root) / 'sets' / demo_set / 'scope.json'
        is_demo = demo.exists() and a['assignment_id'] in groups(root, demo_set)
        category = 'demo' if is_demo else {'training': 'train', 'testing': 'test', 'heldout': 'held-out'}[a['role']]
    return law_directory(a['cell_id'], a['law_id'], category=category, root=root)



def guidance_sources(root, a):
    """Locate prior implementation handoffs without restoring archived directories."""
    from workspaces import work_index
    root = Path(root).resolve()
    index = work_index(root)
    if index.get('format') == 'set-review-workspaces-v2':
        if not index.get('archive_root'):
            return []
        archive = Path(index['archive_root'])
        if not archive.is_absolute():
            archive = root / archive
        archive = archive.resolve()
        old_index = read(archive / 'index.json') if (archive / 'index.json').is_file() else {}
        key = '|'.join((a['cell_id'], a['law_id'], a['actor']))
        entry = old_index.get('assignments', {}).get(key, {})
        category = entry.get('category', {'training': 'train', 'testing': 'test', 'heldout': 'held-out'}[a['role']])
        # Archive root is the former work/ tree, not the artifact root.
        relative = entry.get('path', f"work/{category}/{a['cell_id']}/{a['law_id']}")
        if not relative.startswith('work/'):
            raise ValueError('Unsupported archived workspace locator')
        wp = within(archive, relative[len('work/'):])
    else:
        wp = workspace(root, a, [])
    paths = [wp / 'HANDOFF.md', wp / 'reviewed-finite-assignment-accepted-v1.json']
    active = sorted(wp.glob('ACTIVE-WORK-v*.json'), key=lambda p: p.stat().st_mtime_ns) if wp.exists() else []
    return [p.resolve() for p in [*paths, *active[-1:]] if p.is_file()]


def operation_directory(root, batch_id, package, aid):
    """Implementation/admin packages belong outside the editable review tree."""
    from workspaces import campaign_path, work_index
    root = Path(root).resolve()
    base = campaign_path('worker_exchange', root / 'work') if work_index(root).get('format') == 'set-review-workspaces-v2' else root / 'state/operations/worker_exchange'
    return base / name(batch_id) / name(package) / name(aid)

def local_snapshot(root, a):
    """Relevant membership + completion guidance, not global volatile job counts."""
    memberships, scopes = {}, {}
    for sid in SETS:
        path = Path(root) / 'sets' / sid / 'scope.json'
        if not path.exists() or role(sid) != a['role']:
            continue
        rows = groups(root, sid).get(a['assignment_id'])
        if rows is None:
            continue
        scopes[sid] = sha(path)
        selection = path.parent / 'selection.json'
        members = read(selection).get('members', []) if selection.exists() else []
        memberships[sid] = [m for m in members if all(m.get(k) == a[k] for k in ('law_id', 'cell_id', 'actor'))]
    guidance = {str(path): sha(path) for path in guidance_sources(root, a)}
    catalog = read(Path(root) / 'inputs/catalog/vocabulary_catalog.json')
    cell = next(c for c in catalog['cells'] if c['cell_id'] == a['cell_id'])
    pointer = Path(root) / 'sets/index.json'
    policy = read(pointer).get('law_split_manifest_sha256') if pointer.exists() else None
    law_record = catalog['law_records'].get(a['law_id'])
    if law_record is None:
        corpus = root.parent.parent / 'repo_prep/nevada_sydney/pipeline/traffic-spec-agent/laws/example' / ('test' if a['role']=='heldout' else 'train') / 'laws.jsonl'
        law_record = next((json.loads(line) for line in corpus.read_text().splitlines() if line.strip() and json.loads(line).get('id')==a['law_id']), None)
        if law_record is None:
            raise ValueError('Missing exact active law record')
    return {'scope_hashes': scopes, 'memberships': memberships, 'guidance': guidance,
            'law_sha256': digest(law_record), 'cell_sha256': digest(cell),
            'law_policy_sha256': policy}



def dependency_source(project, root, entry):
    """Explicit read-only dependencies can come from the registered work archive."""
    source_root = entry.get('source_root', 'project')
    if source_root == 'project':
        base = Path(project)
    elif source_root == 'archive':
        from workspaces import work_index
        reference = work_index(root).get('archive_root')
        if not reference:
            raise ValueError('No registered archive root for dependency')
        base = Path(reference)
        if not base.is_absolute():
            base = Path(root) / base
    else:
        raise ValueError('Unknown dependency source_root')
    return within(base, entry['source'])

def _copy_text(source, target):
    text = inspect_file(source)
    if target.exists():
        raise ValueError('Duplicate packaged path: ' + str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def _git_identity(project):
    def git(*args):
        p = subprocess.run(['git', '-C', str(project), *args], capture_output=True, text=True)
        return p.stdout.strip() if p.returncode == 0 else None
    return {'commit': git('rev-parse', 'HEAD'), 'dirty': bool(git('status', '--porcelain'))}


def export(project, root, partition_files, spec_file, destination, batch_id, max_workers=4):
    project, root, destination = Path(project).resolve(), Path(root).resolve(), Path(destination)
    name(batch_id)
    bootstrap = destination.exists()
    if bootstrap:
        initial = check(destination)
        if initial['batch_id'] != 'unassigned' or read(destination / 'batch.json')['assignments']:
            raise ValueError('Destination contains a batch; use a new clean checkout')
        git = _git_identity(destination)
        if git['commit'] and git['dirty']:
            raise ValueError('Commit the untouched bootstrap before exporting into it')
    if not 1 <= max_workers <= 4 or not partition_files:
        raise ValueError('Select partitions and one to four workers')
    spec = read(spec_file)
    tasks, partition_values = {}, []
    for path in partition_files:
        value = read(path)
        if value['format'] != 'worker-partition-v1' or sha(scope_path(root, value['set_id'])) != value['scope_sha256']:
            raise ValueError('Stale/invalid partition: ' + str(path))
        name(value['partition_id'])
        if any(v['partition_id'] == value['partition_id'] for v in partition_values):
            raise ValueError('Duplicate partition id')
        partition_values.append(value)
        available = groups(root, value['set_id'])
        if not value['assignment_ids'] or len(set(value['assignment_ids'])) != len(value['assignment_ids']):
            raise ValueError('Empty/duplicate partition assignments')
        for aid in value['assignment_ids']:
            if aid not in available:
                raise ValueError('Assignment is outside scope: ' + aid)
            rows = available[aid]
            task = tasks.setdefault(aid, {'assignment_id': aid, **{k: rows[0][k] for k in ('law_id', 'cell_id', 'actor')},
                                         'role': role(value['set_id']), 'set_ids': [], 'branches': []})
            if value['set_id'] in task['set_ids']:
                raise ValueError('Assignment allocated twice within a set: ' + aid)
            task['set_ids'].append(value['set_id'])
            task['branches'].extend(rows)
    if set(spec['assignments']) != set(tasks):
        raise ValueError('Export spec must describe exactly the selected assignments')
    catalog_path = root / 'inputs/catalog/vocabulary_catalog.json'
    catalog = read(catalog_path)
    cells = {c['cell_id']: c for c in catalog['cells']}
    # Build off to the side; failures never leave a half-exported checkout.
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix='.worker-export-') as temporary:
        out = Path(temporary) / 'repo'
        out.mkdir()
        assignments = {}
        frozen_sources = {}
        for aid, task in tasks.items():
            cfg = spec['assignments'][aid]
            if not cfg.get('objective') or not cfg.get('dependency_review'):
                raise ValueError('Each assignment needs objective and explicit dependency_review')
            snapshot = local_snapshot(root, task)
            accepted = any(m.get('status') == 'accepted' for ms in snapshot['memberships'].values() for m in ms)
            if accepted and not cfg.get('remaining_requirement'):
                raise ValueError('Existing accepted evidence: specify the remaining requirement; do not replay: ' + aid)
            task.update(objective=cfg['objective'], remaining_requirement=cfg.get('remaining_requirement'),
                        dependency_review=cfg['dependency_review'], external_imports=cfg.get('external_imports', []),
                        local_snapshot=snapshot, cell=cells[task['cell_id']],
                        law_record=catalog['law_records'][task['law_id']])
            task['observation_terms_contract'] = (
                'Summary required_observations are law-planning terms, not Core IDs. '
                'Map every term to measured evidence; put only supported pinned ontology IDs in config.required_atoms.'
            )
            # The upstream law summary calls these "atom" even when they are
            # derived legal predicates. Do not export that misleading key as
            # an executable Core field.
            summary = task.get('summary')
            if isinstance(summary, dict):
                task['source_observation_terms'] = [
                    {'term': item['atom'], 'note': item.get('note', '')}
                    for item in summary.get('required_observations', [])
                ]
                task['summary'] = {key: value for key, value in summary.items()
                                   if key != 'required_observations'}
            witnesses = []
            for row in task['branches']:
                if not row.get('source') or 'source_index' not in row:
                    raise ValueError('Assignment lacks exact witness provenance')
                src = within(root, row['source'])
                if sha(src) != row['source_sha256']:
                    raise ValueError('Witness source changed')
                data = read(src)
                if isinstance(data, dict):
                    data = data.get('witnesses', data.get('coverage_witnesses'))
                if not isinstance(data, list):
                    raise ValueError('Unsupported witness container; supply a supported source')
                witness = data[row['source_index']]
                if witness.get('law', witness.get('law_id', task['law_id'])) != task['law_id'] or witness.get('actor', task['actor']) != task['actor']:
                    raise ValueError('Witness law/actor does not match assignment')
                witnesses.append({'source': row['source'], 'index': row['source_index'],
                                  'source_sha256': row['source_sha256'], 'witness': data[row['source_index']]})
            write(out / 'inputs' / aid / 'assignment.json', task)
            write(out / 'inputs' / aid / 'witnesses.json', witnesses)
            for source in snapshot['guidance']:
                _copy_text(Path(source), out / 'inputs' / aid / 'prior' / Path(source).name)
            # Review files are editable user outputs, not locked freshness inputs.
            review = workspace(root, task, task['set_ids'])
            for filename in ('README.md', 'review.json'):
                if (review / filename).is_file():
                    _copy_text(review / filename, out / 'inputs' / aid / 'review-context' / filename)
            for entry in cfg.get('files', []):
                # Inputs and implementation seeds have separate immutable locations.
                source = dependency_source(project, root, entry)
                dest = within(out / 'inputs' / aid / 'dependencies', entry['destination'])
                _copy_text(source, dest)
                frozen_sources[f'{aid}/{entry["destination"]}'] = {'source': entry['source'], 'source_root': entry.get('source_root', 'project'),
                    'editable_review_context': source.resolve().is_relative_to((root / 'work').resolve()), 'sha256': sha(source)}
            (out / 'work' / aid).mkdir(parents=True)
            assignments[aid] = {'set_ids': task['set_ids'], 'partition_ids': [p['partition_id'] for p in partition_values if aid in p['assignment_ids']],
                                'input_sha256': sha(out / 'inputs' / aid / 'assignment.json')}
        for value in partition_values:
            write(out / 'partitions' / (value['partition_id'] + '.json'), value)
        _runtime(project, out)
        batch = {'format': 'worker-batch-v1', 'batch_id': batch_id, 'max_workers': max_workers,
                 'return_branch': 'worker/' + batch_id, 'assignments': assignments,
                 'source_git': _git_identity(project), 'source_files': frozen_sources,
                 'policy': 'prepare_only_no_sqlite_no_gpu_no_canonical_acceptance',
                 'frozen_files': tree(out)}
        write(out / 'batch.json', batch)
        check(out)
        receipt_path = root / 'inputs/worker_exchange' / batch_id / 'export.json'
        receipt = {'batch': batch, 'batch_sha256': sha(out / 'batch.json'), 'project_root': str(project)}
        if receipt_path.exists() and read(receipt_path) != receipt:
            raise ValueError('Batch id already exported with different inputs')
        if bootstrap:
            for file in out.rglob('*'):
                if file.is_file():
                    target = destination / file.relative_to(out)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(file, target)
        else:
            shutil.move(str(out), str(destination))
    # The trusted export baseline stays local, outside the worker-controlled Git tree.
    receipt = {'batch': batch, 'batch_sha256': sha(destination / 'batch.json'), 'project_root': str(project)}
    receipt_path = root / 'inputs/worker_exchange' / batch_id / 'export.json'
    if receipt_path.exists() and read(receipt_path) != receipt:
        raise ValueError('Batch id already exported with different inputs')
    write(receipt_path, receipt)
    return receipt


def check_return(root, repo, batch_id):
    baseline = read(Path(root) / 'inputs/worker_exchange' / name(batch_id) / 'export.json')
    if sha(Path(repo) / 'batch.json') != baseline['batch_sha256']:
        raise ValueError('Worker changed batch manifest')
    if baseline['batch'].get('gpu_ready_required'):
        current_split = read(Path(root) / 'sets/index.json').get('law_split_version')
        if current_split != baseline['batch'].get('law_split_version'):
            raise ValueError('Law split changed; export a fresh batch')
    for source in baseline['batch']['source_files'].values():
        if source.get('editable_review_context'):
            continue  # Review edits never gate implementation imports.
        path = dependency_source(baseline['project_root'], root, source)
        if not path.is_file() or sha(path) != source['sha256']:
            raise ValueError('Local dependency changed; reconcile before import: ' + source['source'])
    if baseline['batch'].get('gpu_ready_required'):
        from .preparation import check as check_preparation
        result = check_preparation(repo, complete=True, require_ready=True)
    else:
        result = check(repo, complete=True)
    for aid in baseline['batch']['assignments']:
        a = read(Path(repo) / 'inputs' / aid / 'assignment.json')
        expected_snapshot = baseline.get('local_snapshots', {}).get(aid, a.get('local_snapshot'))
        actual = local_snapshot(root, a)
        if expected_snapshot is not None and actual != expected_snapshot:
            extension = Path(root)/'inputs/planning'/('worker-coverage-'+batch_id)/'receipt.json'
            if not extension.exists():
                raise ValueError('Local progress/scope changed; explicitly re-export/reconcile: ' + aid)
            applied = read(extension)
            if applied['package_sha256'] != result['package_sha256'] or any(
                    digest(read(Path(root)/'sets'/sid/'scope.json')) != checksum
                    for sid,checksum in applied['after'].items()):
                raise ValueError('Scope differs from validated worker extension')
            actual = dict(actual, scope_hashes=expected_snapshot['scope_hashes'])
            if actual != expected_snapshot:
                raise ValueError('Local evidence or assignment changed after export: '+aid)
    return result


def preflight_return(root, repo, batch_id, native_python):
    """Check every selected bundle in Native Python without contacting CARLA."""
    checked = check_return(root, repo, batch_id)
    repo = Path(repo).resolve()
    native_python = Path(native_python).resolve()
    from .preparation import runtime_for
    from .execution_manifest import validate
    from .runtime_cli import materialize
    runtime = runtime_for(repo, read(repo / 'batch.json'))
    project = Path(root).resolve().parents[1]
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join((str(runtime / 'scenario_pipeline'), str(runtime / 'python'),
        str(project / 'scripts'), str(project / 'third_party/carla_scene_graphs'),
        str(project / 'carla/PythonAPI/carla'), env.get('PYTHONPATH', '')))
    imports = subprocess.run([str(native_python), '-c',
        'import carla,numpy,shapely,networkx,PIL,carla_sgg'], env=env,
        capture_output=True, text=True, timeout=30)
    if imports.returncode:
        raise ValueError('Native dependency preflight failed: ' + imports.stderr[-1000:])
    results = []
    with tempfile.TemporaryDirectory(prefix='worker-native-preflight-') as temporary:
        for aid in checked['results']:
            manifest = validate(repo, aid)
            path = repo / 'work' / aid / 'execution-manifest.json'
            for entry in manifest['cases']:
                case = entry['case_id']
                destination = Path(temporary) / case
                proposal = materialize(path, case, destination)
                runner = within(destination, proposal['entrypoint'])
                run = subprocess.run([str(native_python), str(runner), '--check'],
                    cwd=destination, env=env, capture_output=True, text=True, timeout=300)
                if run.returncode:
                    raise ValueError('Native offline preflight failed for ' + case + ': ' + (run.stderr + run.stdout)[-1000:])
                results.append({'case_id': case, 'construction_sha256': entry['construction_sha256'],
                                'runner_sha256': sha(runner),
                                'stdout_sha256': hashlib.sha256(run.stdout.encode()).hexdigest()})
    return {'batch_id': batch_id, 'native_python': str(native_python),
            'runtime_manifest_sha256': sha(runtime / 'SOURCE-MANIFEST.json'),
            'imports_passed': True, 'cases': results, 'carla_contacted': False,
            'campaign_attempt_created': False}


def import_return(root, repo, batch_id):
    checked = check_return(root, repo, batch_id)
    batch = read(Path(repo) / 'batch.json')
    package = checked['package_sha256']
    receipt_path = Path(root) / 'inputs/worker_exchange' / batch_id / ('import-' + package + '.json')
    if receipt_path.exists():
        previous = read(receipt_path)
        local_checkout = Path(previous.get('local_checkout', '')).resolve()
        if (Path(repo).resolve() == local_checkout and previous.get('package_sha256') == package
                and tree(repo) == checked['files']):
            return previous
    # Do not imply a commit identity if the return has uncommitted changes.
    git = _git_identity(repo)
    if not git['commit'] or git['dirty']:
        raise ValueError('Commit the returned package before importing')
    destinations = {}
    for aid in checked['results']:
        target = operation_directory(root, batch_id, package, aid)
        destinations[aid] = str(target)
        source = Path(repo) / 'work' / aid
        if target.exists():
            if tree(target) != tree(source):
                raise ValueError('Existing import differs; refusing overwrite')
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=target.parent, prefix='.import-') as tmp:
                staging = Path(tmp) / aid
                shutil.copytree(source, staging)
                if tree(staging) != tree(source):
                    raise ValueError('Return changed during import')
                staging.rename(target)
    shared = Path(repo)/'work/_shared'
    if shared.exists():
        target = Path(root)/'state/operations/worker_exchange'/batch_id/package/'_shared'
        if target.exists() and tree(target)!=tree(shared):
            raise ValueError('Shared import conflict')
        if not target.exists():
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(shared,target)
        pass  # shared implementation is materialized by canonical inline construction files
    # Preserve the worker's portable execution layout locally.  The flattened
    # assignment imports above support stage adoption; this complete checkout
    # supplies runtime.py, overlay.py, inputs and work/_shared without Git or
    # access to the remote worker repository.  Runtime scratch stays in state/.
    local_checkout = operation_directory(root, batch_id, package, 'local-checkout')
    if local_checkout.exists():
        if tree(local_checkout) != checked['files']:
            raise ValueError('Local checkout import differs; refusing overwrite')
    else:
        local_checkout.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=local_checkout.parent, prefix='.local-checkout-') as tmp:
            staging = Path(tmp) / 'checkout'
            staging.mkdir()
            for relative, checksum in checked['files'].items():
                source, destination = within(repo, relative), within(staging, relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                if sha(destination) != checksum:
                    raise ValueError('Local checkout copy differs: ' + relative)
            staging.rename(local_checkout)
    if tree(repo) != checked['files'] or _git_identity(repo) != git:
        raise ValueError('Return changed during import; no acceptance recorded')
    receipt = {'format': 'worker-import-v1', 'batch_id': batch_id, 'package_sha256': package,
               'return_git': git, 'destinations': destinations,
        'local_checkout': str(local_checkout),
        'local_checkout_manifest_sha256': digest(checked['files']),
               'results': checked['results'], 'status': 'prepared_only',
               'next': 'Review imported code/tests locally; use adopt with an explicit local stage plan. No jobs dispatched.'}
    if receipt_path.exists() and read(receipt_path) != receipt:
        raise ValueError('Import receipt conflict')
    write(receipt_path, receipt)
    return receipt


def _runtime(project, out):
    for skill in (*SKILLS, 'worker-preparation'):
        _copy_text(project / 'scenario_pipeline/skills' / skill / 'SKILL.md',
                   out / 'runtime/skills' / skill / 'SKILL.md')
    for doc in ('storage.md', 'batch_pipeline.md', 'large_scale_production.md'):
        _copy_text(project / 'scenario_pipeline/docs' / doc, out / 'runtime/docs' / doc)
    from batch_pipeline.stages import CONTRACTS
    write(out / 'runtime/stage_contracts.json', CONTRACTS)
    for filename in ('__init__.py', 'common.py', 'portable.py', 'media.py', 'capture.py'):
        target = out / 'runtime/worker_exchange' / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((MODULE / filename).read_text())
    for filename in ('START_HERE.md', 'worker_check.py', 'test_portable.py'):
        target = out / ('tests/test_portable.py' if filename == 'test_portable.py' else filename)
        _copy_text(MODULE / 'templates' / filename, target)
    (out / '.gitignore').write_text('__pycache__/\n*.py[cod]\n.pytest_cache/\n')


def init_worker(project, destination):
    """Create a Git-ready empty repository. No real assignments or DB are exported."""
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Destination exists; refusing to overwrite')
    destination.mkdir(parents=True)
    _runtime(Path(project), destination)
    for directory in ('partitions', 'inputs', 'work'):
        (destination / directory).mkdir(exist_ok=True)
    write(destination / 'batch.json', {
        'format': 'worker-batch-v1', 'batch_id': 'unassigned', 'max_workers': 4,
        'return_branch': 'worker/unassigned', 'assignments': {},
        'policy': 'No tasks assigned. Stop after portable checks.',
        'frozen_files': tree(destination)})
    return {'destination': str(destination), 'assignments': [], 'git_initialized': False,
            'next': 'Assign explicit work before sharing. No real campaign data exported.'}


def refresh_scaffold(project, destination):
    """Refresh only a verified unassigned scaffold; never overwrite worker results."""
    destination = Path(destination)
    current = check(destination)
    if current['batch_id'] != 'unassigned' or read(destination / 'batch.json')['assignments']:
        raise ValueError('Only an unchanged, unassigned scaffold can be refreshed')
    old_files = tree(destination)
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix='.worker-scaffold-') as tmp:
        staged = Path(tmp) / 'repo'
        init_worker(project, staged)
        replacement = tree(staged)
        if tree(destination) != old_files:
            raise ValueError('Scaffold changed during refresh')
        for rel in old_files.keys() - replacement.keys():
            within(destination, rel).unlink()
        for rel in replacement:
            target = within(destination, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(staged / rel, target)
    check(destination)
    return {'destination': str(destination), 'assignments': [], 'refreshed': True}
