"""Build three distinct physical-risk alternatives per exact sign-angle case."""

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / 'sign-angle-compatibility-manifest.json'

PLANS = {
    'fallback1': {
        'trigger': {
            'source': 'control_inventory.jsonl and capture/evidence.jsonl',
            'metric': 'original Native sign-trigger polygon overlap with the governed approach lane',
            'failure_condition': 'sign trigger does not cover the lane at the approach waypoint',
        },
        'changed_knobs': ['OpenDRIVE signal lateral t from -3.8 m to -3.4 m; authored face angle fixed'],
        'files': {'native-map-plan/yield-nearest-view.xodr':
                  ('t="-3.8"', 't="-3.4"')},
    },
    'fallback2': {
        'trigger': {
            'source': 'reference_corner.mkv',
            'metric': 'original camera frames with visible yield-sign face and governed lane',
            'failure_condition': 'sign face and governed lane are not both visible in required original frames',
        },
        'changed_knobs': ['reference-corner camera origin and pitch for sign-face framing'],
        'files': {'runner.py':
                  ("'reference_corner': pose(19, -25, 15, 135, -24)",
                   "'reference_corner': pose(23, -28, 18, 135, -27)")},
    },
    'fallback3': {
        'trigger': {
            'source': 'approach_history.jsonl',
            'metric': 'original frames of sign-governed ego approach before junction entry',
            'failure_condition': 'fewer than 40 original approach frames are retained before junction entry',
        },
        'changed_knobs': ['ego OpenDRIVE approach spawn from x=-60 m to x=-70 m'],
        'files': {
            'yield_construction.py':
                ('EGO_POINT = opendrive_to_carla(-60.0, -1.8)',
                 'EGO_POINT = opendrive_to_carla(-70.0, -1.8)'),
            'tests/test_yield_construction.py':
                ('(-60, 1.8): (158190, -1, False)',
                 '(-70, 1.8): (158190, -1, False)'),
        },
    },
}


def main():
    manifest = json.loads(MANIFEST.read_text())
    if len(manifest['cases']) != 3:
        raise ValueError('Three sign-angle exact cases required')
    for entry in manifest['cases']:
        primary = json.loads((ROOT / entry['construction']).read_text())
        folder = (ROOT / entry['construction']).parent / 'fallbacks'
        folder.mkdir(exist_ok=True)
        candidates = []
        for ident, plan in PLANS.items():
            candidate = copy.deepcopy(primary)
            files = {item['path']: item for item in candidate['files']}
            for name, (old, new) in plan['files'].items():
                item = files[name]
                if item['content'].count(old) != 1:
                    raise ValueError(entry['case_id'] + ': ' + ident + ' missing unique anchor')
                item['content'] = item['content'].replace(old, new)
                item.pop('source', None)
            if ident == 'fallback1':
                test = files['tests/test_sign_angle.py']
                test['content'] = test['content'].replace(
                    '        self.assertAlmostEqual(float(sign.attrib["hOffset"]),',
                    '        self.assertAlmostEqual(float(sign.attrib["t"]), -3.4)\n'
                    '        self.assertAlmostEqual(float(sign.attrib["hOffset"]),')
            if ident == 'fallback2':
                test = files['tests/test_sign_angle.py']
                test['content'] += (
                    '\n    def test_reference_camera_change(self):\n'
                    '        runner = (Path(__file__).resolve().parents[1] / "runner.py").read_text()\n'
                    '        self.assertIn("reference_corner\': pose(23, -28, 18, 135, -27)", runner)\n')
            path = folder / f'{ident}-construction.json'
            path.write_text(json.dumps(candidate, indent=2) + '\n')
            candidates.append({'id': ident,
                               'construction': str(path.relative_to(ROOT)),
                               'construction_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                               'trigger': plan['trigger'],
                               'changed_knobs': plan['changed_knobs']})
        entry['candidates'] = candidates
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': 3, 'fallbacks': 9}))


if __name__ == '__main__':
    main()
