"""Stage all selected C150142 Native constructions on the current runtime.

This draft preserves canonical selection and receipts until affected proofs can
be rerun. It never marks a candidate ready or rewrites the selected manifest.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OUT = ROOT / 'current-runtime-runner-drafts'
REPLACEMENTS = (
    ('runtime/pipeline/scenario_pipeline', 'runtime/scenario_pipeline'),
    ('runtime/pipeline/python', 'runtime/python'),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_atomic(path, data):
    scratch = REPO / '.runtime-work/owner150142/runner-draft-tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=scratch,
                                     prefix='runner-', delete=False) as stream:
        stream.write(json.dumps(data, sort_keys=True, indent=2) + '\n')
        temporary = Path(stream.name)
    os.replace(temporary, path)


def run():
    manifest_path = ROOT / 'execution-manifest.json'
    draft = json.loads(manifest_path.read_text())
    rows = []
    for entry in draft['cases']:
        case = entry['case_id'].removeprefix(ROOT.name + '__')
        for candidate, field in [('primary', entry),
                                 *[(item['id'], item) for item in entry['candidates']]]:
            source_path = ROOT / field['construction']
            construction = json.loads(source_path.read_text())
            runner = next(item for item in construction['files']
                          if item['path'] == 'runner.py')
            old = runner['content']
            new = old
            for before, after in REPLACEMENTS:
                new = new.replace(before, after)
            if new == old or 'runtime/pipeline/' in new:
                raise ValueError('Expected retired Native runtime import in '
                                 + case + '/' + candidate)
            runner['content'] = new
            target = OUT / case / candidate / 'construction.json'
            write_atomic(target, construction)
            field['construction'] = str(target.relative_to(ROOT))
            field['construction_sha256'] = sha(target)
            field.pop('offline', None)
            rows.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                         'source_construction_sha256': sha(source_path),
                         'draft_construction': field['construction'],
                         'draft_construction_sha256': field['construction_sha256']})
    if len(rows) != 120:
        raise ValueError('Expected all 30 primary and 90 fallback constructions')
    draft['status'] = 'draft'
    draft['delivery_ready'] = False
    draft_path = ROOT / 'current-runtime-runner-draft-manifest.json'
    write_atomic(draft_path, draft)
    return {'format': 'c150142-current-runner-draft-index-v1',
            'passed': True, 'selected_manifest_sha256': sha(manifest_path),
            'draft_manifest_sha256': sha(draft_path),
            'candidate_count': len(rows), 'cases': len(draft['cases']),
            'scope': 'current-runtime Native source staging; CPU proofs pending',
            'original_native_observed': False}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2, sort_keys=True))
