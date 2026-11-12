"""Build three source-hashed physical-risk alternatives for each exact case."""

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / 'execution-manifest.json'

CHANGES = {
    'fallback1': {
        'files': {
            'yield_construction.py': (
                'EGO_POINT = opendrive_to_carla(-60.0, -1.8)',
                'EGO_POINT = opendrive_to_carla(-50.0, -1.8)'),
            'tests/test_yield_construction.py': (
                '(-60, 1.8): (158190, -1, False)',
                '(-50, 1.8): (158190, -1, False)'),
        },
        'trigger': {
            'source': 'interaction_history.jsonl',
            'metric': 'last original frame with ego body fully outside the junction',
            'failure_condition': 'ego body has not fully exited the junction by original frame 599',
        },
        'changed_knobs': ['ego approach spawn from OpenDRIVE x=-60 m to x=-50 m'],
    },
    'fallback2': {
        'files': {'runner.py': (
            "'reference_corner': pose(19, -25, 15, 135, -24)",
            "'reference_corner': pose(23, -28, 18, 135, -27)")},
        'trigger': {
            'source': 'reference_corner.mkv',
            'metric': 'source-camera frames with yield sign face and through-highway approach visible',
            'failure_condition': 'original reference-corner frames do not show the sign face and through-highway approach together',
        },
        'changed_knobs': ['reference_corner camera origin (19,-25,15) to (23,-28,18) m and pitch -24 to -27 degrees'],
    },
    'fallback3': {
        'files': {'yield_controller.py': (
            'def speed_control(target_mps, observed_mps, *, gain=.25):',
            'def speed_control(target_mps, observed_mps, *, gain=.4):')},
        'trigger': {
            'source': 'approach_history.jsonl',
            'metric': 'absolute original-frame ego speed error versus constructed target near closest view',
            'failure_condition': 'measured ego speed differs from the case target by more than 1 m/s near closest view',
        },
        'changed_knobs': ['bounded longitudinal speed-control gain from 0.25 to 0.4'],
    },
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        primary = json.loads((ROOT / entry['construction']).read_text())
        folder = (ROOT / entry['construction']).parent / 'fallbacks'
        folder.mkdir(exist_ok=True)
        candidates = []
        for ident, plan in CHANGES.items():
            candidate = copy.deepcopy(primary)
            for file in candidate['files']:
                if file['path'] in plan['files']:
                    old, new = plan['files'][file['path']]
                    if file['content'].count(old) != 1:
                        raise ValueError(f'{entry["case_id"]}: {ident} missing unique anchor {old}')
                    file['content'] = file['content'].replace(old, new)
            path = folder / f'{ident}-construction.json'
            path.write_text(json.dumps(candidate, indent=2) + '\n')
            candidates.append({
                'id': ident,
                'construction': str(path.relative_to(ROOT)),
                'construction_sha256': sha(path),
                'trigger': plan['trigger'],
                'changed_knobs': plan['changed_knobs'],
            })
        entry['candidates'] = candidates
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(manifest['cases']),
                      'fallbacks': sum(len(x['candidates']) for x in manifest['cases'])}))


if __name__ == '__main__':
    main()
