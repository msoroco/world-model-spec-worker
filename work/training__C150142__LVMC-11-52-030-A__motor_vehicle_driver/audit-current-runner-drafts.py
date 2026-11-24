"""Independently compare all current-runtime Native drafts with selected sources."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CURRENT = ROOT / 'current-runtime-runner-draft-manifest.json'
SELECTED = ROOT / 'execution-manifest.json'
OLD = ('runtime/pipeline/scenario_pipeline', 'runtime/pipeline/python')
NEW = ('runtime/scenario_pipeline', 'runtime/python')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_map(entry):
    return {'primary': entry, **{item['id']: item for item in entry['candidates']}}


def check():
    selected = json.loads(SELECTED.read_text())
    current = json.loads(CURRENT.read_text())
    if selected['assignment_id'] != current['assignment_id'] or \
            [item['case_id'] for item in selected['cases']] != \
            [item['case_id'] for item in current['cases']]:
        raise ValueError('Current draft changes exact selected case inventory')
    rows = []
    for old_entry, new_entry in zip(selected['cases'], current['cases']):
        before, after = candidate_map(old_entry), candidate_map(new_entry)
        if set(before) != set(after):
            raise ValueError('Current draft changes candidate inventory')
        for candidate in before:
            old_field, new_field = before[candidate], after[candidate]
            old_path, new_path = ROOT / old_field['construction'], ROOT / new_field['construction']
            if old_field['construction_sha256'] != sha(old_path) or \
                    new_field['construction_sha256'] != sha(new_path):
                raise ValueError('Construction binding differs')
            original = json.loads(old_path.read_text())
            draft = json.loads(new_path.read_text())
            old_files = {item['path']: item['content'] for item in original['files']}
            new_files = {item['path']: item['content'] for item in draft['files']}
            if set(old_files) != set(new_files):
                raise ValueError('Draft changes construction file inventory')
            for path, content in old_files.items():
                expected = content
                if path == 'runner.py':
                    for prior, active in zip(OLD, NEW):
                        expected = expected.replace(prior, active)
                if expected != new_files[path]:
                    raise ValueError('Draft changed source beyond runtime import: '
                                     + old_entry['case_id'] + '/' + candidate + '/' + path)
            a = dict(original)
            b = dict(draft)
            a.pop('files'); b.pop('files')
            if a != b:
                raise ValueError('Draft changed non-source construction fields')
            if any(prior in new_files['runner.py'] for prior in OLD):
                raise ValueError('Draft retains retired runtime import')
            rows.append({'case_id': old_entry['case_id'], 'candidate_id': candidate,
                         'selected_sha256': sha(old_path), 'draft_sha256': sha(new_path)})
    if len(rows) != 120:
        raise ValueError('Expected complete current runner inventory')
    return {'format': 'c150142-current-runner-draft-audit-v1',
            'passed': True, 'candidate_count': len(rows),
            'selected_manifest_sha256': sha(SELECTED),
            'draft_manifest_sha256': sha(CURRENT),
            'rows': rows, 'original_native_observed': False}


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True, indent=2))
