"""Bundle the authored one-way Native junction over source-bound exact requests."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE_DIR = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    base = json.loads((CASE_DIR / 'draft-request-manifest.json').read_text())
    entries = []
    for old in base['cases']:
        proposal = json.loads((CASE_DIR / old['construction']).read_text())
        if sha(CASE_DIR / old['construction']) != old['construction_sha256']:
            raise ValueError('Source-bound request changed')
        proposal['entrypoint'] = 'runner.py'
        proposal['files'].extend([
            {'path': 'runner.py', 'content': (HERE / 'runner.py').read_text()},
            {'path': 'crossroads.xodr', 'content': (HERE / 'crossroads.xodr').read_text()}])
        proposal['static_checks'] = ['one-way two-roadway OpenDRIVE junction',
            'authored two uncovered signal heads', 'four 600-frame original camera encoders',
            'Native actor motion and world restoration']
        proposal['status'] = 'selected_native_cpu_draft_not_delivery_prepared'
        suffix = old['case_id'].rsplit('__', 1)[-1]
        path = HERE / 'native-bundles' / suffix / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proposal, indent=2) + '\n')
        entries.append({'case_id': old['case_id'], 'kind': 'delivery',
            'construction': str(path.relative_to(CASE_DIR)),
            'construction_sha256': sha(path),
            'candidate_risk': {'status': 'physical',
                'reason': 'Original map signal, actor stop and driver-view survey may fail'},
            'candidates': [], 'delivery_readiness': 'incomplete'})
    manifest = {'format': 'worker-selected-cpu-draft-manifest-v1',
        'assignment_id': CASE_DIR.name, 'status': 'partial', 'cases': entries,
        'physical_acceptance_claimed': False}
    (CASE_DIR / 'draft-native-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_ids': [e['case_id'] for e in entries],
                      'construction_sha256': [e['construction_sha256'] for e in entries]}))


if __name__ == '__main__':
    build()
