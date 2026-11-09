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
            'format': 'worker-partition', 'partition_id': f'{set_id}-{n+1:02d}',
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
    root = Path(root).resolve()
    base = root/'state/operations/worker_exchange'
    return base / name(batch_id) / name(package) / name(aid)

def resolve_law(project, root, law_id, catalog_value=None):
    """Resolve exact law text independently of the assignment's cell partition."""
    catalog = Path(root)/'inputs/catalog/vocabulary_catalog.json'
    law = (catalog_value if catalog_value is not None else read(catalog))['law_records'].get(law_id)
    if law is not None:
        return law, {'path': str(catalog), 'sha256': sha(catalog)}
    base = Path(project)/'repo_prep/nevada_sydney/pipeline/traffic-spec-agent/laws/example'
    matches = []
    for partition in ('train', 'test'):
        source = base/partition/'laws.jsonl'
        if source.is_file():
            for line in source.read_text().splitlines():
                if line.strip():
                    record = json.loads(line)
                    if record.get('id') == law_id:
                        matches.append((record, {'path': str(source), 'sha256': sha(source)}))
    if not matches or any(row[0] != matches[0][0] for row in matches):
        raise ValueError('Missing or conflicting exact law source: '+law_id)
    return matches[0]


def retained_binding(root, row, cache):
    """Read retained data, not legacy executable code, from a verified import."""
    reference = row['worker_binding']
    batch, package = name(reference['batch_id']), name(reference['package_sha256'])
    key = (batch, package)
    if key not in cache:
        receipt_path = Path(root)/'inputs/worker_exchange'/batch/('import-'+package+'.json')
        receipt = read(receipt_path)
        if receipt.get('package_sha256') != package or receipt.get('batch_id') != batch:
            raise ValueError('Supplemental binding import identity mismatch')
        checkout = operation_directory(root, batch, package, 'local-checkout')
        if digest(tree(checkout)) != receipt.get('local_checkout_manifest_sha256'):
            raise ValueError('Supplemental binding source changed: '+batch)
        matrix_path = checkout/'work/_shared/branch-coverage.json'
        review_path = checkout/'work/_shared/branch-review.json'
        matrix, review = read(matrix_path), read(review_path)
        if (review.get('coverage_sha256') != sha(matrix_path) or
                review.get('missing_branches') != [] or not review.get('review_method')):
            raise ValueError('Supplemental binding lacks a source-bound completed review')
        cache[key] = (checkout, matrix, {'import_sha256': sha(receipt_path),
                       'coverage_sha256': sha(matrix_path), 'review_sha256': sha(review_path),
                       'reviewer': review.get('reviewer'), 'review_method': review['review_method']})
    checkout, matrix, provenance = cache[key]
    aid = assignment_id(row, row['_role'])
    bindings = [b for b in matrix['additional_bindings'] if b['assignment_id'] == aid]
    source = checkout/'work'/aid/'assignment.json'
    assignment = read(source)
    if (len(bindings) != 1 or not bindings[0].get('binding_reason') or
            not bindings[0].get('original_cell_incompatibility') or
            any(assignment.get(k) != row[k] for k in ('law_id','cell_id','actor')) or
            assignment.get('branch') != row.get('branch')):
        raise ValueError('Supplemental binding identity/reason mismatch: '+aid)
    return {'source': str(source), 'source_sha256': sha(source),
            'provenance_status': 'source_bound_imported_review', 'review': provenance,
            'binding': bindings[0], 'witness': assignment}


def local_snapshot(root, a, project=None):
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
    law_record, _ = resolve_law(Path(project) if project else MODULE.parent.parent, root, a['law_id'], catalog)
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
    if not 1 <= max_workers <= 8 or not partition_files:
        raise ValueError('Select partitions and one to eight workers')
    spec = read(spec_file)
    tasks, partition_values = {}, []
    for path in partition_files:
        value = read(path)
        if value['format'] != 'worker-partition' or sha(scope_path(root, value['set_id'])) != value['scope_sha256']:
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
    binding_cache, law_cache = {}, {}
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
            summary = cfg.get('summary')
            if not isinstance(summary, dict) or summary.get('id') != task['law_id']:
                raise ValueError('Each assignment needs its explicit exact-law summary; historical campaign defaults are retired')
            snapshot = local_snapshot(root, task, project)
            accepted = any(m.get('status') == 'accepted' for ms in snapshot['memberships'].values() for m in ms)
            if accepted and not cfg.get('remaining_requirement'):
                raise ValueError('Existing accepted evidence: specify the remaining requirement; do not replay: ' + aid)
            if task['law_id'] not in law_cache:
                law_cache[task['law_id']] = resolve_law(project, root, task['law_id'], catalog)
            law_record, task['law_record_source'] = law_cache[task['law_id']]
            task.update(objective=cfg['objective'], remaining_requirement=cfg.get('remaining_requirement'),
                        dependency_review=cfg['dependency_review'], external_imports=cfg.get('external_imports', []),
                        local_snapshot=snapshot, cell=cells[task['cell_id']],
                        law=law_record)
            task['summary'] = dict(summary)
            task['summary_status'] = 'provided_planning_context_full_text_remains_authoritative'
            if task['role'] == 'training':
                task['selection_targets'] = (['demo-train'] if aid in groups(root, 'demo-train') else []) + ['full-train']
            elif task['role'] == 'testing':
                task['selection_targets'] = (['demo-test'] if aid in groups(root, 'demo-test') else []) + ['full-test']
            else:
                task['selection_targets'] = ['held-out']
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
                if row.get('worker_binding'):
                    witnesses.append(retained_binding(root, dict(row, _role=task['role']), binding_cache))
                    continue
                if row.get('source') == 'preserved_accepted_membership':
                    witnesses.append({'source': 'preserved_accepted_membership',
                        'provenance_status': 'membership_only_current_requirement_unreviewed',
                        'witness': {'law': row['law_id'], 'actor': row['actor'],
                                    'cell': row['cell_id'], 'recording_ids': row.get('recording_ids', []),
                                    'coverage_status': row['coverage_status']}})
                    continue
                if not row.get('source') or 'source_index' not in row:
                    raise ValueError('Assignment lacks exact witness provenance')
                src = within(root, row['source'])
                if sha(src) != row['source_sha256']:
                    raise ValueError('Witness source changed')
                data = read(src)
                if isinstance(data, dict):
                    data = data.get('witnesses', data.get('coverage_witnesses', data.get('laws')))
                if not isinstance(data, list):
                    raise ValueError('Unsupported witness container; supply a supported source')
                witness = data[row['source_index']]
                if witness.get('law', witness.get('law_id', task['law_id'])) != task['law_id'] or witness.get('actor', task['actor']) != task['actor']:
                    raise ValueError('Witness law/actor does not match assignment')
                witnesses.append({'source': row['source'], 'index': row['source_index'],
                                  'source_sha256': row['source_sha256'], 'witness': data[row['source_index']]})
            recordings = {}
            for sid, members in snapshot['memberships'].items():
                for member in members:
                    if member.get('status') != 'accepted':
                        continue
                    rid = name(member['recording_id'])
                    entry = recordings.setdefault(rid, {'recording_id': rid, 'sets': [],
                        'membership': member, 'coverage_status': 'requires_source_review', 'sources': []})
                    entry['sets'].append(sid)
                    metadata = root/'recordings'/rid/'metadata.json'
                    if metadata.is_file() and not entry['sources']:
                        target = out/'inputs'/aid/'accepted'/rid/'metadata.json'
                        _copy_text(metadata, target)
                        entry['sources'].append({'path': str(target.relative_to(out)),
                                                 'sha256': sha(target)})
            write(out/'inputs'/aid/'evidence.json', {
                'recordings': list(recordings.values()),
                'requested_remaining_requirement': cfg.get('remaining_requirement'),
                'instruction': 'Review sources and full law; document exact demonstrated facts, unknowns and gaps. Accepted membership alone does not establish full statutory coverage.'})
            write(out / 'inputs' / aid / 'assignment.json', task)
            write(out / 'inputs' / aid / 'witnesses.json', witnesses)
            for source in snapshot['guidance']:
                _copy_text(Path(source), out / 'inputs' / aid / 'prior' / Path(source).name)
            # Review files are editable user outputs, not locked freshness inputs.
            review = workspace(root, task, task['set_ids'])
            if (review / 'README.md').is_file():
                _copy_text(review / 'README.md', out / 'inputs' / aid / 'review-context' / 'README.md')
            relative=review.relative_to(root/'work')
            if len(relative.parts)==2:
                model=root/'state/review_models'/relative.parts[0]/(relative.parts[1]+'.json')
                if model.is_file():
                    _copy_text(model, out / 'inputs' / aid / 'review-context' / 'review.json')
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
        laws = {task['law_id']: {'law': task['law'],
                    'topics': {'exact-text': task['law']['text']},
                    'source': task['law_record_source']} for task in tasks.values()}
        write(out/'inputs/coverage/branch-sources.json', {'laws': laws})
        allocations = {}
        for sid in SETS:
            path = scope_path(root, sid)
            if path.is_file():
                for row in read(path)['assignments']:
                    allocations.setdefault(row['cell_id'], set()).add(sid)
        write(out/'inputs/coverage/candidate-cells.json', {
            'catalog_sha256': sha(catalog_path),
            'cells': [dict(cell, allocated_sets=sorted(allocations.get(cell['cell_id'], [])))
                      for cell in catalog['cells']]})
        for value in partition_values:
            write(out / 'partitions' / (value['partition_id'] + '.json'), value)
        runtime = _runtime(project, out)
        batch = {'format': 'worker-batch', 'mode':'six_step_preparation', 'runtime':runtime,
                 'full_branch_coverage_required': True, 'gpu_ready_required': True,
                 'law_split_version': read(root/'sets/index.json').get('law_split_version') if (root/'sets/index.json').is_file() else None,
                 'max_return_files': max(1000, len(assignments)*200),
                 'update_version':0, 'batch_id': batch_id, 'max_workers': max_workers,
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


# Cache only package readiness within one synchronous preparation command.
# Local snapshots, dependencies and canonical recording checks still run each time.
from contextvars import ContextVar
from contextlib import contextmanager
_readiness_cache = ContextVar('worker_return_readiness_cache', default=None)

@contextmanager
def preparation_validation_scope():
    token = _readiness_cache.set({})
    try:
        yield
    finally:
        _readiness_cache.reset(token)

def _ready_package(repo, checker):
    cache = _readiness_cache.get()
    base = Path(repo).resolve()
    def fingerprint():
        rows = []
        for directory, dirs, files in os.walk(base):
            relative_dir = Path(directory).relative_to(base)
            dirs[:] = [part for part in dirs if part not in ('.git', '__pycache__', '.pytest_cache')
                       and not (relative_dir == Path('.') and part in ('.venv', '.venv-cpu', '.runtime-work'))]
            for name in sorted(dirs + files):
                path = Path(directory)/name
                if path.suffix == '.pyc':
                    continue
                st = path.lstat()
                rows.append((str(path.relative_to(base)), st.st_dev, st.st_ino,
                             st.st_mode, st.st_size, st.st_mtime_ns, st.st_ctime_ns,
                             os.readlink(path) if path.is_symlink() else None))
        return tuple(sorted(rows))
    before = fingerprint()
    key = str(base)
    if cache is not None and key in cache:
        saved, result = cache[key]
        if saved != before:
            raise ValueError('Imported package changed during preparation')
        return result
    # The imported checkout was fully validated when its immutable import
    # receipt was created. Reuse that static result only while every source
    # inode, size and modification/change timestamp still matches the
    # validated snapshot. Local selection memberships are checked separately
    # by _check_return on every call and may grow after acceptance.
    cache_path = base.parent/'validated-static-return-v1.json' if base.name == 'local-checkout' else None
    if cache_path is not None and cache_path.is_file():
        saved = read(cache_path)
        result = saved.get('result', {})
        valid_receipt = (saved.get('format') == 'validated-static-return-v1'
                         and saved.get('checkout') == str(base)
                         and result.get('package_sha256') == base.parent.name
                         and digest(result.get('files', {})) == result['package_sha256'])
        if valid_receipt and saved.get('fingerprint_sha256') != digest(before):
            # Directory timestamps can change as delivery work is materialized.
            # Verify the imported file contents before adopting a new fast cache.
            expected = result['files']
            actual = {row[0] for row in before if (base / row[0]).is_file()}
            if actual != set(expected) or any(
                    not (base / relative).is_file() or sha(base / relative) != checksum
                    for relative, checksum in expected.items()):
                raise ValueError('Imported package differs from validated static snapshot')
            if fingerprint() != before:
                raise ValueError('Imported package changed during readiness validation')
            saved['fingerprint_sha256'] = digest(before)
            write(cache_path, saved)
        if valid_receipt and saved.get('fingerprint_sha256') == digest(before):
            if cache is not None:
                cache[key] = (before, result)
            return result
        raise ValueError('Imported package differs from validated static snapshot')
    result = checker(repo, complete=True, require_ready=True)
    if fingerprint() != before:
        raise ValueError('Imported package changed during readiness validation')
    if cache_path is not None:
        if result['package_sha256'] != base.parent.name:
            raise ValueError('Validated local checkout differs from imported package')
        write(cache_path, {'format': 'validated-static-return-v1', 'checkout': str(base),
                           'fingerprint_sha256': digest(before), 'result': result})
    if cache is not None:
        cache[key] = (before, result)
    return result

def check_return(root, repo, batch_id):
    # A preparation command adopts one validated starting snapshot. Its internal
    # registrations only write local DB stages and frozen child inputs; they do
    # not acquire new evidence or alter the imported return or set membership.
    # Execution and acceptance run outside this scope and validate independently.
    cache = _readiness_cache.get()
    if cache is None:
        return _check_return(root, repo, batch_id)
    key = ('validated-starting-return', str(Path(root).resolve()),
           str(Path(repo).resolve()), batch_id)
    if key not in cache:
        cache[key] = _check_return(root, repo, batch_id)
    return cache[key]


def _recording_identity(recording):
    """Cheap identity of every accepted canonical file after full verification."""
    rows = []
    for directory, dirs, files in os.walk(recording):
        dirs[:] = [part for part in dirs if part != '__pycache__']
        for name in sorted(dirs + files):
            path = Path(directory)/name
            if path.suffix == '.pyc':
                continue
            st = path.lstat()
            rows.append((str(path.relative_to(recording)), st.st_dev, st.st_ino,
                         st.st_mode, st.st_size, st.st_mtime_ns, st.st_ctime_ns,
                         os.readlink(path) if path.is_symlink() else None))
    return digest(tuple(sorted(rows)))


def _verify_accepted_once(recording, cache_dir):
    from recording_store import verify_recording
    recording = Path(recording).resolve()
    cache_path = cache_dir/(recording.name + '.json')
    before = _recording_identity(recording)
    if cache_path.is_file():
        saved = read(cache_path)
        if (saved.get('format') == 'validated-accepted-recording-v1'
                and saved.get('recording_id') == recording.name
                and saved.get('identity_sha256') == before
                and saved.get('metadata_sha256') == sha(recording/'metadata.json')):
            return
        # Evidence may be appended after an earlier cache was written. Recheck
        # the complete canonical recording before refreshing its fast identity.
        if (saved.get('format') != 'validated-accepted-recording-v1'
                or saved.get('recording_id') != recording.name):
            raise ValueError('Accepted canonical recording cache is invalid: '+recording.name)
    verify_recording(recording)
    if _recording_identity(recording) != before:
        raise ValueError('Accepted canonical recording changed during validation: '+recording.name)
    cache_dir.mkdir(parents=True, exist_ok=True)
    write(cache_path, {'format': 'validated-accepted-recording-v1',
                       'recording_id': recording.name, 'identity_sha256': before,
                       'metadata_sha256': sha(recording/'metadata.json')})


def _check_return(root, repo, batch_id):
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
        result = _ready_package(repo, check_preparation)
    else:
        result = check(repo, complete=True)
    for aid in baseline['batch']['assignments']:
        a = read(Path(repo) / 'inputs' / aid / 'assignment.json')
        expected_snapshot = baseline.get('local_snapshots', {}).get(aid, a.get('local_snapshot'))
        actual = local_snapshot(root, a, baseline['project_root'])
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
                # Accepted delivery recordings from this same return are expected
                # to accumulate after export. Preserve the original snapshot for
                # every other field and verify each added membership against its
                # canonical recording and the frozen case manifest.
                if a['role'] != 'testing':
                    raise ValueError('Local evidence or assignment changed after export: '+aid)
                manifest = read(Path(repo)/'work'/aid/'execution-manifest.json')
                allowed = {case['case_id'] for case in manifest['cases']
                           if case.get('kind') == 'delivery'}
                previous = expected_snapshot['memberships']
                current = actual['memberships']
                additions = {}
                for sid in ('demo-test', 'full-test'):
                    before = previous.get(sid, [])
                    after = current.get(sid, [])
                    # Selection writers may reorder members while appending an
                    # accepted recording. The exported members are immutable,
                    # but their position in the growing selection is not.
                    from collections import Counter
                    old = Counter(digest(member) for member in before)
                    new = Counter(digest(member) for member in after)
                    if old - new:
                        raise ValueError('Prior membership changed after export: '+aid)
                    remaining = old.copy()
                    additions[sid] = []
                    for member in after:
                        key = digest(member)
                        if remaining[key]:
                            remaining[key] -= 1
                        else:
                            additions[sid].append(member)
                if Counter(digest(m) for m in additions['demo-test']) != Counter(digest(m) for m in additions['full-test']):
                    raise ValueError('Post-export test selections differ: '+aid)
                for member in additions['full-test']:
                    rid = member.get('recording_id')
                    if (member.get('status') != 'accepted' or member.get('case_id') not in allowed
                            or not isinstance(rid, str) or len(rid) != 64):
                        raise ValueError('Unrecognized post-export delivery member: '+aid)
                    recording = Path(root)/'recordings'/rid
                    metadata = read(recording/'metadata.json')
                    if (metadata.get('status') != 'accepted' or metadata.get('recording_id') != rid
                            or metadata.get('case_id') != member['case_id']
                            or metadata.get('cell_id') != a['cell_id']
                            or metadata.get('law_id') != a['law_id']
                            or metadata.get('actor') != a['actor']):
                        raise ValueError('Post-export member lacks matching canonical acceptance: '+aid)
                    cache_dir = Path(root)/'state/operations/worker_exchange'/batch_id/result['package_sha256']/'validated-recordings'
                    _verify_accepted_once(recording, cache_dir)
                reconciled = dict(actual, memberships=previous)
                if reconciled != expected_snapshot:
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
    cache_key = digest({'package_sha256': checked['package_sha256'],
                        'runtime_manifest_sha256': sha(runtime / 'SOURCE-MANIFEST.json'),
                        'native_python': str(native_python),
                        'native_python_sha256': sha(native_python)})
    receipt = Path(root)/'state/operations/worker_exchange'/batch_id/'preflight-cache'/f'{cache_key}.json'
    if receipt.is_file():
        saved = read(receipt)
        if saved.get('cache_key') == cache_key and saved.get('result', {}).get('cases'):
            return saved['result']
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
    result = {'batch_id': batch_id, 'native_python': str(native_python),
            'runtime_manifest_sha256': sha(runtime / 'SOURCE-MANIFEST.json'),
            'imports_passed': True, 'cases': results, 'carla_contacted': False,
            'campaign_attempt_created': False}
    write(receipt, {'format': 'native-preflight-cache', 'cache_key': cache_key,
                    'result': result})
    return result


def import_return(root, repo, batch_id):
    checked = check_return(root, repo, batch_id)
    batch = read(Path(repo) / 'batch.json')
    package = checked['package_sha256']
    receipt_path = Path(root) / 'inputs/worker_exchange' / batch_id / ('import-' + package + '.json')
    if receipt_path.exists():
        previous = read(receipt_path)
        local_checkout = Path(previous.get('local_checkout', '')).resolve()
        if (Path(repo).resolve() == local_checkout and previous.get('package_sha256') == package
                and digest(checked['files']) == previous.get('local_checkout_manifest_sha256')):
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
    receipt = {'format': 'worker-import', 'batch_id': batch_id, 'package_sha256': package,
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
    from .export_runtime import export as export_pipeline_runtime
    runtime = out/'runtime'
    export_pipeline_runtime(project, runtime)
    for skill in (*SKILLS, 'worker-preparation'):
        _copy_text(project/'scenario_pipeline/skills'/skill/'SKILL.md',
                   runtime/'skills'/skill/'SKILL.md')
    for doc in ('storage.md', 'batch_pipeline.md', 'delivery_workflow.md'):
        _copy_text(project/'scenario_pipeline/docs'/doc, runtime/'docs'/doc)
    from batch_pipeline.stages import CONTRACTS
    write(runtime/'stage_contracts.json', CONTRACTS)
    for filename in ('START_HERE.md','FULL_BRANCH_CONTRACT.md','DELIVERY_CONTRACT.md',
                     'worker_check.py','runtime_launcher.py','test_portable.py'):
        target = out/('runtime.py' if filename=='runtime_launcher.py' else
                      'tests/test_portable.py' if filename=='test_portable.py' else filename)
        _copy_text(MODULE/'templates'/filename, target)
    (out/'.gitignore').write_text('__pycache__/\n*.py[cod]\n.pytest_cache/\n.runtime-work/\n.venv*/\n')
    # Skills and contracts are part of the same immutable runtime.
    files = tree(runtime)
    files.pop('SOURCE-MANIFEST.json', None)
    write(runtime/'SOURCE-MANIFEST.json', {'source':'main scenario_pipeline','files':files,
          'policy':'Source-hashed portable preparation; execution and acceptance remain local'})
    return {'root':'runtime','source_manifest_sha256':sha(runtime/'SOURCE-MANIFEST.json'),
            'package_compatibility_required':True}


def init_worker(project, destination):
    """Create a Git-ready empty repository. No real assignments or DB are exported."""
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Destination exists; refusing to overwrite')
    destination.mkdir(parents=True)
    runtime = _runtime(Path(project), destination)
    for directory in ('partitions', 'inputs', 'work'):
        (destination / directory).mkdir(exist_ok=True)
    write(destination / 'batch.json', {
        'format': 'worker-batch', 'mode':'six_step_preparation', 'runtime':runtime,
        'update_version':0, 'batch_id': 'unassigned', 'max_workers': 4,
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
