"""Bind the two exact device responses to current-runtime candidate sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def candidate(suffix, name):
    stem = f'current-v3-{suffix}-{name}'
    path = HERE / f'{stem}-construction.json'
    return {
        'id': name,
        'construction': path.name,
        'construction_sha256': sha(path),
        'trigger': {
            'source': 'original Native body trajectory and source camera review',
            'metric': 'device station crossing and readable face pixels',
            'failure_condition': ('requested stop or crossing not physically realized'
                                  if name == 'fallback1' else 'device face or approach obscured'),
        },
        'changed_knobs': ['route_policy' if name == 'fallback1' else 'camera_policy'],
    }


def main():
    cases = []
    for suffix in ('probe_1', 'probe_2'):
        primary = candidate(suffix, 'primary')
        cases.append({
            'case_id': HERE.name + '__' + suffix,
            'kind': 'draft_not_selected',
            'construction': primary['construction'],
            'construction_sha256': primary['construction_sha256'],
            'measurement_contract': f'current-v3-{suffix}-primary-measurement-contract.json',
            'measurement_procedure': {'entrypoint': 'finalize.py',
                                      'output_schema': 'c10389-device-current-v2-analysis'},
            'fixture_recipe': f'work/{HERE.name}/current-v3-{suffix}-primary-recipe.json',
            'candidate_risk': {'status': 'physical',
                               'reason': 'Original station motion and device-face visibility require review'},
            'candidates': [candidate(suffix, name) for name in ('fallback1', 'fallback2')],
        })
    manifest = {'format': 'worker-unselected-current-v3-probe-manifest',
                'assignment_id': HERE.name,
                'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'status': 'draft_not_selected', 'cases': cases}
    out = HERE / 'current-v3-draft-manifest.json'
    out.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest': str(out), 'sha256': sha(out), 'cases': len(cases)}))


if __name__ == '__main__':
    main()
