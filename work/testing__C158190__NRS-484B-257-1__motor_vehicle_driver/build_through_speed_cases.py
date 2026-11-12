"""Build exact, unselected scalar through-speed cases from the selected primary.

The original construction and selected manifest remain immutable. These drafts
have their own embedded Native runner/config and can be offline materialized.
"""

import hashlib
import json
from pathlib import Path

from through_speed_sweep import TARGETS_MPS

ROOT = Path(__file__).resolve().parent
PREFIX = 'testing__C158190__NRS-484B-257-1__motor_vehicle_driver__'
OLD = 'yield_nearest_view_through_approaches'


def replace_strings(value, old, new):
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, list):
        return [replace_strings(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: replace_strings(item, old, new) for key, item in value.items()}
    return value


def build():
    template = json.loads((ROOT / 'construction.json').read_text())
    cases = []
    for target in TARGETS_MPS:
        speed = int(target)
        suffix = f'yield_nearest_view_through_speed_{speed}'
        construction = replace_strings(template, OLD, suffix)
        files = {entry['path']: entry for entry in construction['files']}
        motion = files['yield_motion.py']
        old_target = 'THROUGH_TARGET_MPS = 7.0'
        assert motion['content'].count(old_target) == 1
        motion['content'] = motion['content'].replace(old_target,
                                                      f'THROUGH_TARGET_MPS = {target:.1f}')
        test = files['tests/test_yield_motion.py']
        old_assertion = "self.assertEqual(slow['through_target_mps'], 7.)"
        assert test['content'].count(old_assertion) == 1
        test['content'] = test['content'].replace(old_assertion,
                                                  f"self.assertEqual(slow['through_target_mps'], {target:.1f})")
        if target < 4.0:
            old_control = "self.assertGreater(through.control['throttle'], 0)"
            assert test['content'].count(old_control) == 1
            test['content'] = test['content'].replace(
                old_control, "self.assertGreater(through.control['brake'], 0)")
        config = json.loads(files['config.json']['content'])
        assert config['selected_case_id'] == PREFIX + suffix
        assert config['supported_case_ids'][0] == PREFIX + suffix
        assert f'THROUGH_TARGET_MPS = {target:.1f}' in motion['content']
        path = ROOT / f'cases/through_speed_{speed}/construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        (path.parent / 'config.json').write_text(files['config.json']['content'])
        path.write_text(json.dumps(construction, indent=2) + '\n')
        cases.append({'case_id': PREFIX + suffix,
                      'construction': str(path.relative_to(ROOT)),
                      'construction_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'kind': 'diagnostic_unselected',
                      'through_speed_target_mps': target})
    manifest = {'format': 'worker-execution-manifest-draft',
                'assignment_id': PREFIX.removesuffix('__'),
                'cases': cases,
                'limitation': 'Offline scalar construction only; no Native feasibility, pixels, or legal hazard cutoff.'}
    path = ROOT / 'through-speed-draft-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'draft_cases': len(cases), 'targets_mps': list(TARGETS_MPS)}))


if __name__ == '__main__':
    build()
