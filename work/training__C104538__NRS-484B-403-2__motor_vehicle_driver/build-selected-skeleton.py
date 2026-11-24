"""Promote the tested 30-second constructions into an exact delivery draft.

This only binds source bytes. Proof receipts are attached after rerunning the
selected public checks; synthetic sources never assert Native success.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    draft = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    entries = []
    for source in draft['cases']:
        suffix = source['case_id'].rsplit('__', 1)[-1]
        primary = json.loads((HERE / source['construction']).read_text())
        root = HERE if suffix == 'witness_1' else HERE / 'cases' / suffix
        for item in primary['files']:
            dest = root / item['path']
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(item['content'])
        selected = {
            'case_id': source['case_id'],
            'kind': 'delivery',
            'construction': source['construction'],
            'construction_sha256': sha(HERE / source['construction']),
            'candidate_risk': {
                'status': 'physical',
                'reason': 'Observed route error or original sign/body pixel coverage may fail in Native capture'
            },
            'candidates': [c for c in source['candidates'] if c['id'] in ('fallback1', 'fallback3')],
            'measurement_contract': f'current-v2-{suffix}-measurement-contract.json',
            'measurement_procedure': source['measurement_procedure'],
            'fixture_recipe': f'work/{HERE.name}/v2-{suffix}-recipe.json',
            'native_handoff': {
                'python_env_var': 'CARLA_PYTHON',
                'host_env_var': 'CARLA_HOST',
                'port_env_var': 'CARLA_PORT'
            },
        }
        entries.append(selected)
    manifest = {
        'format': 'worker-execution-manifest',
        'assignment_id': HERE.name,
        'runtime_manifest_sha256': draft['runtime_manifest_sha256'],
        'cases': entries,
    }
    write(HERE / 'execution-manifest.json', manifest)
    plan = json.loads((HERE / 'case-plan.json').read_text())
    plan['selected_branch'] = 'Duty to obey an applicable official U-turn prohibition.'
    plan['camera_plan'] = {
        'profile': 'overview1080-capability',
        'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'hill approach, sign and complete ego movement', 'interval': 'all 600 frames'},
            {'view': 'approach', 'subject': 'approach lane and source sign pixels', 'interval': 'all 600 frames'},
            {'view': 'reference_corner', 'subject': 'official-device cue and governed region', 'interval': 'all 600 frames'},
            {'view': 'driver_reference', 'subject': 'forward road context', 'interval': 'all 600 frames'},
        ],
    }
    for case in plan['cases']:
        case['kind'] = 'delivery'
    write(HERE / 'case-plan.json', plan)
    proposals = json.loads((HERE / 'proposals/cases.json').read_text())
    proposals['status'] = 'draft'
    proposals.setdefault('sweep_specs', [])
    for case in proposals['cases']:
        case['kind'] = 'delivery'
        case['rationale'] = 'Controlled source measurement of signed U-turn behavior; legal applicability requires original review'
        case['recording_description'] = json.loads((HERE / next(e['construction'] for e in entries if e['case_id'] == case['case_id'])).read_text())['recording_description']
    write(HERE / 'proposals/cases.json', proposals)
    print(json.dumps({'manifest_sha256': sha(HERE / 'execution-manifest.json'), 'cases': len(entries)}))


if __name__ == '__main__':
    main()
