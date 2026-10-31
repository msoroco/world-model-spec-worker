"""Metadata-only active sets derived from frozen precomputed cell partitions."""
from contextlib import ExitStack
import json
import shutil
from pathlib import Path

from batch_pipeline.store import atomic
from pipeline_paths import OUTPUT_ROOT
from recording_store import identity, locked, sha

ACTIVE = ('demo-train', 'demo-test', 'held-out', 'full-train', 'full-test')
SOURCES = ('demo-v1', 'heldout-v1', 'production-v1', 'production-v2')
FOCUSED = 'inputs/planning/focused-coverage-20261016-v1'
DEMO = FOCUSED + '/demo-continuation-20261017-v32/coverage-worklist.json'


def member_key(member):
    return tuple(member.get(k) for k in ('campaign', 'law_id', 'cell_id', 'actor', 'case_id', 'comparison'))


def organize_sets(root=None):
    root = Path(root) if root is not None else OUTPUT_ROOT
    from law_split import active_manifest
    current=active_manifest(root)
    if current:
        return {'status':'active_version_preserved','version':current['version'],'action':'Use refresh-workspaces; historical bootstrap is disabled'}
    with ExitStack() as stack:
        stack.enter_context(locked(root/'state/set-organization.lock'))
        for name in ACTIVE:
            stack.enter_context(locked(root/'state'/('set-' + name + '.lock')))
        return _organize(root)


def _organize(root):
    sources = {}
    audit = root/'state/storage-verification.json'
    if not audit.is_file() or not json.loads(audit.read_text()).get('all_protected_rows_unchanged'):
        raise ValueError('A successful storage preservation audit is required')

    def read(relative):
        path = root/relative
        sources[relative] = sha(path)
        return json.loads(path.read_text())

    cells = {s: read(FOCUSED + '/' + s + '-cells.json') for s in ('training', 'testing', 'heldout')}
    owners = {}
    for split, values in cells.items():
        for cell in values:
            if cell in owners:
                raise ValueError('Precomputed cell splits overlap: ' + cell)
            owners[cell] = split
    if (root/FOCUSED/'partitions.json').exists():
        partition = read(FOCUSED + '/partitions.json')
        if any(set(partition['selection'][s]) != set(cells[s]) for s in cells):
            raise ValueError('Precomputed partition and cell lists disagree')
    ledger = 'work/demo-thirteen-complete-20261010/PENDING-WORK.txt'
    if (root/ledger).exists():
        sources[ledger] = sha(root/ledger)
    witnesses = read(FOCUSED + '/coverage-witnesses.json')
    demo = read(DEMO)
    laws = {entry['law_id'] for entry in demo['laws']}
    history = {name: read('sets/' + name + '/selection.json')['members'] for name in SOURCES}
    for name in ('demo-five-snapshot', 'demo-parallel-snapshot'):
        if (root/'sets'/name/'selection.json').exists():
            read('sets/' + name + '/selection.json')
    full_laws = {s: sorted({w['law'] for w in witnesses if w['split'] == s}) for s in cells}
    if not laws <= set(full_laws['training']) or not laws <= set(full_laws['testing']):
        raise ValueError('Demo laws lack precomputed training/testing witnesses')
    members = {name: {} for name in ACTIVE}
    excluded = []

    def add(name, member):
        key = member_key(member)
        old = members[name].get(key)
        if old is not None and old != member:
            raise ValueError('Conflicting recording membership: ' + str(key))
        members[name][key] = member

    for member in history['demo-v1']:
        if member['law_id'] not in laws:
            raise ValueError('Demo member outside the reviewed demo law list')
        split = member['split']
        if owners.get(member['cell_id']) != split:
            raise ValueError('Demo member conflicts with precomputed split')
        if split == 'heldout':
            add('held-out', member)
        else:
            suffix = {'training': 'train', 'testing': 'test'}[split]
            add('demo-' + suffix, member)
            add('full-' + suffix, member)

    exceptions = []
    for member in history['heldout-v1']:
        if member['split'] != 'heldout':
            raise ValueError('Historical held-out membership has an unexpected split')
        member = dict(member)
        owner = owners.get(member['cell_id'])
        if owner != 'heldout':
            exception = {'recording_id': member['recording_id'], 'cell_id': member['cell_id'],
                         'precomputed_split': owner, 'retained_split': 'heldout',
                         'reason': 'User-selected historical held-out overlap exception; no training reuse.'}
            member['historical_split_exception'] = exception
            exceptions.append(exception)
        add('held-out', member)

    heldout_ids = {m['recording_id'] for m in members['held-out'].values()}
    for name in ('production-v1', 'production-v2'):
        for original in history[name]:
            member = dict(original)
            split = owners.get(member['cell_id'])
            if (split not in ('training', 'testing') or member['law_id'] not in full_laws.get(split, [])
                    or member['recording_id'] in heldout_ids):
                excluded.append({'source_set': name, 'member': original,
                                 'reason': 'Not compatible with full training/testing scope or reserved as held-out evidence.'})
                continue
            if member['split'] == 'unassigned':
                member['split'] = split
                member['split_provenance'] = {'source': FOCUSED + '/' + split + '-cells.json',
                                             'sha256': sources[FOCUSED + '/' + split + '-cells.json'],
                                             'reason': 'Precomputed cell ownership; historical recording metadata unchanged.'}
            elif member['split'] != split:
                excluded.append({'source_set': name, 'member': original, 'reason': 'Historical split conflicts with precomputed cell ownership.'})
                continue
            add('full-' + {'training': 'train', 'testing': 'test'}[split], member)

    for suffix in ('train', 'test'):
        # Compatible production pairs targeting demo laws also belong to the demo subset.
        for member in list(members['full-' + suffix].values()):
            if member['law_id'] in laws:
                add('demo-' + suffix, member)

    # A recording has one active split, except that the same split is intentionally
    # referenced by its demo subset and its full superset.
    recording_splits = {}
    metadata = {}
    for group in members.values():
        for member in group.values():
            rid = member['recording_id']
            if recording_splits.setdefault(rid, member['split']) != member['split']:
                raise ValueError('A held-out recording cannot also be training/testing evidence')
            if rid not in metadata:
                folder = root/'recordings'/rid
                if Path(rid).name != rid or rid in ('.', '..'):
                    raise ValueError('Invalid recording ID')
                metadata[rid] = json.loads((folder/'metadata.json').read_text())
                for filename in ('video.webm', 'trace.json'):
                    if not (folder/filename).is_file():
                        raise ValueError('Missing primary recording file: ' + str(folder/filename))
                if metadata[rid].get('status') != 'accepted':
                    raise ValueError('Source set references a nonaccepted recording: ' + rid)
            actual = metadata[rid]
            declared_law = actual.get('law_id') or actual.get('published_record', {}).get('law_id')
            if declared_law and declared_law != member['law_id'] and not member.get('reuse_receipt'):
                raise ValueError('Recording law mismatch')
            if actual.get('split') in ('training', 'testing', 'heldout') and actual['split'] != member['split']:
                raise ValueError('Recording split conflicts with active membership')
            if not member.get('reuse_receipt'):
                for field in ('cell_id', 'actor', 'case_id'):
                    if actual.get(field) != member[field]:
                        raise ValueError('Recording identity mismatch: ' + field)

    source_version = identity(sources)
    outputs = {}
    for name in ACTIVE:
        split = 'heldout' if name == 'held-out' else ('training' if name.endswith('train') else 'testing')
        demo_only = name.startswith('demo-')
        target_laws = sorted(laws) if demo_only else full_laws[split]
        assignments = []
        relevant = {}
        for member in members[name].values():
            key = (member['law_id'], member['cell_id'], member['actor'])
            relevant.setdefault(key, set()).add(member['recording_id'])
        for index, witness in enumerate(witnesses):
            if witness['split'] != split or witness['law'] not in target_laws:
                continue
            if owners.get(witness['cell']) != split:
                raise ValueError('Reviewed witness outside precomputed split')
            key = (witness['law'], witness['cell'], witness['actor'])
            assignments.append({'law_id': key[0], 'cell_id': key[1], 'actor': key[2],
                                'requirement': witness.get('requirement'), 'branch': witness.get('branch'),
                                'source': FOCUSED + '/coverage-witnesses.json', 'source_index': index,
                                'source_sha256': sources[FOCUSED + '/coverage-witnesses.json'],
                                'coverage_status': 'pending_review', 'recording_ids': sorted(relevant.get(key, []))})
        if split == 'training':
            for index, law in enumerate(demo['laws']):
                for cell in law.get('reviewed_training_cells', []):
                    if owners.get(cell) != split:
                        raise ValueError('Continuation assignment outside training cells')
                    key = (law['law_id'], cell, law['actor'])
                    assignments.append({'law_id': key[0], 'cell_id': cell, 'actor': key[2],
                                        'source': DEMO, 'source_index': index, 'source_sha256': sources[DEMO],
                                        'coverage_status': 'pending_review', 'recording_ids': sorted(relevant.get(key, []))})
        scope = {'format': 'recording-scope-v1', 'set_id': name, 'source_version': source_version,
                 'split': split, 'law_ids': target_laws,
                 'recorded_law_ids': sorted({m['law_id'] for m in members[name].values()}),
                 'historical_laws_outside_planned_scope': sorted({m['law_id'] for m in members[name].values()} - set(target_laws)),
                 'precomputed_cells_source': FOCUSED + '/' + split + '-cells.json',
                 'precomputed_cell_ids': cells[split],
                 'scope_cell_ids': sorted(({a['cell_id'] for a in assignments} |
                                            {m['cell_id'] for m in members[name].values()}) if demo_only else cells[split]),
                 'cells_without_reviewed_assignments': sorted(set(cells[split]) - {a['cell_id'] for a in assignments}) if not demo_only else [],
                 'assignments': assignments, 'sources': sources,
                 'historical_split_exceptions': exceptions if name == 'held-out' else [],
                 'includes': ['demo-' + name.removeprefix('full-')] if name.startswith('full-') else [],
                 'reviewed_coverage_complete': False}
        selection = {'frozen': True, 'reviewed_coverage_complete': False, 'scope_sha256': identity(scope),
                     'source_version': source_version,
                     'members': sorted(members[name].values(), key=lambda m: json.dumps(member_key(m)))}
        outputs['sets/' + name + '/scope.json'] = scope
        outputs['sets/' + name + '/selection.json'] = selection
    index = {'format': 'active-recording-sets-v1', 'active_sets': list(ACTIVE),
             'historical_sets': sorted(p.name for p in (root/'sets').iterdir()
                                       if p.is_dir() and p.name not in ACTIVE),
             'sources': sources, 'source_version': source_version,
             'cell_disjoint': not exceptions,
             'historical_overlap_recordings': len(exceptions)}
    if (root/'sets/index.json').exists():
        current=json.loads((root/'sets/index.json').read_text())
        for key in ('workspace_index','workspace_categories'):
            if key in current: index[key]=current[key]
    outputs['sets/index.json'] = index
    changed = [rel for rel, value in outputs.items()
               if not (root/rel).exists() or json.loads((root/rel).read_text()) != value]
    receipt_path = root/'state/set-organization.json'
    if not changed and receipt_path.exists():
        return json.loads(receipt_path.read_text())
    for name in ACTIVE:
        if any(rel.startswith('sets/' + name + '/') for rel in changed) and (root/'sets'/name/'completion.json').exists():
            raise ValueError('Cannot reorganize a finalized set: ' + name)
    # Preserve complete preceding active metadata before changing any destination.
    previous = {rel: json.loads((root/rel).read_text()) for rel in outputs if (root/rel).exists()}
    if previous:
        snapshot = root/'inputs/bundles/set-organization'/identity(previous)
        for rel, value in previous.items():
            if not (snapshot/rel).exists():
                (snapshot/rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root/rel, snapshot/rel)
    for rel in changed:
        atomic(root/rel, outputs[rel])
    receipt = {'completed': True, 'source_version': source_version, 'sources': sources,
               'output_hashes': {rel: sha(root/rel) for rel in outputs},
               'sets': {name: {'members': len(members[name]),
                              'recordings': len({m['recording_id'] for m in members[name].values()}),
                              'planned_laws': len(outputs['sets/' + name + '/scope.json']['law_ids']),
                              'planned_cells': len(outputs['sets/' + name + '/scope.json']['scope_cell_ids'])} for name in ACTIVE},
               'historical_overlap_recordings': len(exceptions), 'excluded': excluded,
               'native_executions': 0, 'payload_copies': 0, 'finalization_deferred': True,
               'preservation_audit': {'source': 'state/storage-verification.json', 'sha256': sha(audit)}}
    atomic(receipt_path, receipt)
    return receipt
