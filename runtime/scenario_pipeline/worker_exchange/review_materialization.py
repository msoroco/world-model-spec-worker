"""Materialize an accepted delivery in the editable review workspaces."""

import json
import os
import shutil
from pathlib import Path

from recording_store import locked, sha
from lean_work import FORMAT, case_folder, folder


def _read(path):
    return json.loads(Path(path).read_text())


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.delivery-tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def _copy_verified(source, target, expected):
    if not target.exists():
        temporary = target.with_name(target.name + '.delivery-tmp')
        shutil.copy2(source, temporary)
        if sha(temporary) != expected:
            temporary.unlink()
            raise ValueError('Review copy differs from accepted canonical media')
        temporary.replace(target)
    if sha(target) != expected:
        raise ValueError('Existing review output differs from accepted canonical media: ' + str(target))


def materialize(root, repo, assignment, case_id, recording_id, targets):
    """Add exact accepted outputs, model rows, and index entries before refresh.

    This is idempotent. Existing review files are verified and never overwritten.
    The model records unresolved legal judgments; physical comparison receipts
    remain a separate acceptance requirement.
    """
    root, repo = Path(root), Path(repo)
    if set(targets) != {'demo-test', 'full-test'}:
        raise ValueError('This review materializer requires both testing selections')
    canonical = root / 'recordings' / recording_id
    metadata = _read(canonical / 'metadata.json')
    acceptance = metadata['acceptance']
    if (metadata.get('status') != 'accepted' or metadata.get('recording_id') != recording_id
            or metadata.get('case_id') != case_id or acceptance.get('law_id') != assignment['law_id']):
        raise ValueError('Canonical acceptance identity differs')
    member = None
    for set_id in targets:
        matches = [row for row in _read(root / 'sets' / set_id / 'selection.json')['members']
                   if row.get('recording_id') == recording_id and row.get('case_id') == case_id
                   and row.get('status') == 'accepted']
        if len(matches) != 1:
            raise ValueError('Exact accepted membership missing: ' + set_id)
        member = matches[0]
    group, case_name = folder(member), case_folder(member)
    full = root / 'work/full-test' / group / case_name
    demo = root / 'work/demo-test' / group / case_name
    with locked(root / 'state/review-materialization.lock'):
        full.mkdir(parents=True, exist_ok=True)
        evidence = canonical / 'evidence'
        _copy_verified(evidence / 'raw.mkv', full / 'video.webm', acceptance['video_sha256'])
        _copy_verified(evidence / 'traffic_spec/trace.json', full / 'trace.json', acceptance['trace_sha256'])
        review = {'schema': 'final-review-recording-v1', 'recording_id': recording_id,
                  'case_id': case_id, 'law_id': assignment['law_id'], 'status': 'accepted',
                  'frames': acceptance['frames'], 'video_sha256': acceptance['video_sha256'],
                  'trace_sha256': acceptance['trace_sha256'], 'expected_label': None,
                  'judgment_sweep': False}
        from shared_manifest import canonical_path, link as link_manifest, link_sets
        if canonical_path(root).is_file():
            link_sets(root)
            link_manifest(root, full)
            review['manifest_sha256'] = sha(canonical_path(root))
        review_path = full / 'metadata.json'
        if review_path.exists():
            current = _read(review_path)
            if any(current.get(key) != value for key, value in review.items()):
                raise ValueError('Existing review metadata differs from accepted recording')
        else:
            _write(review_path, review)
        demo.parent.mkdir(parents=True, exist_ok=True)
        relative = os.path.relpath(full, demo.parent)
        if demo.is_symlink():
            if os.readlink(demo) != relative:
                raise ValueError('Existing demo review link differs')
        elif demo.exists():
            raise ValueError('Demo review path is not a shared link')
        else:
            demo.symlink_to(relative, target_is_directory=True)

        specs_path = repo / 'work' / assignment['assignment_id'] / 'comparison-audit-specs.json'
        specs = _read(specs_path) if specs_path.is_file() else []
        if isinstance(specs, dict):
            specs = specs.get('comparisons', [])
        relevant = [spec for spec in specs if case_id in spec.get('case_ids', [])]
        for set_id in targets:
            model_path = root / 'state/review_models' / set_id / (group + '.json')
            model = (_read(model_path) if model_path.exists() else
                     {'law': assignment['law'], 'cell_id': assignment['cell_id'],
                      'law_id': assignment['law_id'], 'comparisons': []})
            if model.get('cell_id') != assignment['cell_id'] or model.get('law_id') != assignment['law_id']:
                raise ValueError('Review model identity differs')
            for spec in relevant or [{'comparison_id': case_id, 'case_ids': [case_id]}]:
                comparison_id = spec['comparison_id']
                matches = [row for row in model['comparisons'] if row['id'] == comparison_id]
                if len(matches) > 1:
                    raise ValueError('Duplicate review comparison')
                if matches:
                    comparison = matches[0]
                else:
                    comparison = {'id': comparison_id,
                                  'title': comparison_id.replace('_', ' ').capitalize(), 'cases': []}
                    model['comparisons'].append(comparison)
                existing = [row for row in comparison['cases'] if row['case_id'] == case_id]
                if existing and (len(existing) != 1 or existing[0]['recording_id'] != recording_id):
                    raise ValueError('Review comparison references another recording')
                if not existing:
                    comparison['cases'].append({'recording_id': recording_id, 'case_id': case_id,
                                                'description': case_id.rsplit('__', 1)[-1].replace('_', ' '),
                                                'judgments': ['Legal applicability and priority unresolved'],
                                                'reuse': False})
            _write(model_path, model)

        index_path = root / 'work/index.json'
        index = _read(index_path)
        if index.get('format') != FORMAT:
            raise ValueError('Unsupported review index')
        for set_id in targets:
            matches = [row for row in index['entries'] if row['set_id'] == set_id and row['folder'] == group]
            if len(matches) > 1:
                raise ValueError('Duplicate review group')
            if matches:
                entry = matches[0]
                if entry['cell_id'] != assignment['cell_id'] or entry['law_id'] != assignment['law_id']:
                    raise ValueError('Review index identity differs')
            else:
                entry = {'set_id': set_id, 'folder': group, 'cell_id': assignment['cell_id'],
                         'law_id': assignment['law_id'], 'recording_ids': [],
                         'path': 'work/' + set_id + '/' + group}
                index['entries'].append(entry)
            if recording_id not in entry['recording_ids']:
                entry['recording_ids'].append(recording_id)
        _write(index_path, index)
    return {'recording_id': recording_id, 'sets': list(targets), 'group': group,
            'comparison_ids': [spec['comparison_id'] for spec in relevant]}
