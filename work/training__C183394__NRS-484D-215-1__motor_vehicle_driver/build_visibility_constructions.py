"""Assemble two exact visibility-trigger Native bundles and physical fallbacks."""
import hashlib
import json
from pathlib import Path

from build_constructions import DESCRIPTION


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'native'
AID = ROOT.name
CASES = ('visibility_dim', 'visibility_high')
MODULES = ('runner.py', 'beam_capture.py', 'beam_native.py', 'beam_scene.py',
           'visibility_scene.py', 'saved_beam.py', 'oncoming_beam.py', 'finalize.py')


def source(name):
    value = (SOURCE / name).read_text()
    if name in ('runner.py', 'beam_native.py'):
        value = value.replace('from beam_scene import ', 'from visibility_scene import ')
    if name == 'beam_native.py':
        old = 'precipitation=0, fog_density=0))'
        new = 'precipitation=0, fog_density=plan["lighting"]["fog_density_request"]))'
        if old not in value:
            raise ValueError('Native fog seam changed')
        value = value.replace(old, new)
        value = value.replace('speed < 2.5 else 0', 'speed < 3.0 else 0')
        value = value.replace('speed > 3 else 0', 'speed > 3.5 else 0')
    if name == 'beam_capture.py':
        old = 'not case.endswith(\n            ("__condition_a", "__condition_b"))'
        new = 'case.rsplit("__", 1)[-1] not in ("visibility_dim", "visibility_high")'
        if old not in value:
            raise ValueError('Capture case seam changed')
        value = value.replace(old, new)
        old = '"condition_a" if case.endswith("__condition_a")\n                        else "condition_b"'
        new = 'case.rsplit("__", 1)[-1]'
        if old not in value:
            raise ValueError('Capture scene seam changed')
        value = value.replace(old, new)
        old = '''"lighting_trigger": "night_interval",
            "original_trigger_source": "original simulator weather request and timestamp; dated Nevada sun-event review pending",
            "NRS_484D_100_review_required": True,
            "civil_time_condition_verified": False'''
        new = '''"lighting_trigger": "poor_visibility",
            "original_trigger_source": "controlled fog request and original oncoming actor; decoded 1000-foot discernibility review pending",
            "NRS_484D_100_review_required": True,
            "authored_initial_target_ft": 1000,
            "original_target_actor_id": scene["oncoming"].id,
            "original_target_transform_m": [scene["oncoming"].get_transform().location.x,
                                            scene["oncoming"].get_transform().location.y],
            "discernibility_verified": False'''
        if old not in value:
            raise ValueError('Capture trigger seam changed')
        value = value.replace(old, new)
    return value


def build():
    ids = [AID + '__' + case for case in CASES]
    for case in CASES:
        for candidate, gain in (('primary', .20), ('fallback1', .26)):
            case_id = AID + '__' + case
            config = {'selected_case_id': case_id, 'supported_case_ids': ids,
                      'cell_id': 'C183394', 'law_id': 'NRS-484D-215-1',
                      'actor': 'motor_vehicle_driver', 'candidate_id': candidate,
                      'beam_mode': 'dim_within_500' if case == 'visibility_dim' else 'retain_high',
                      'rate_hz': 20, 'duration_s': 30,
                      'acceleration_gain': gain, 'requested_speed_mps': 3.0,
                      'required_atoms': [], 'source_packets': [],
                      'cameras': ['overview', 'approach', 'driver_reference', 'reference_corner'],
                      'case': {'recording_description': DESCRIPTION},
                      'recording_description': DESCRIPTION}
            test = '''import unittest
from pathlib import Path
from runner import check
from visibility_scene import request, validate_request

class Offline(unittest.TestCase):
    def test_exact_visibility_pair(self):
        bundle = Path(__file__).resolve().parents[1]
        outcome = check(bundle)
        self.assertEqual(outcome['frames'], 600)
        self.assertFalse(outcome['physical_success_claimed'])
        suffix = outcome['case_id'].rsplit('__', 1)[-1]
        self.assertEqual(validate_request(request(suffix))['target_ft'], 1000)
'''
            files = [{'path': name, 'content': source(name)} for name in MODULES]
            files.extend([{'path': 'config.json', 'content': json.dumps(config, indent=2)+'\n'},
                          {'path': 'tests/test_offline.py', 'content': test}])
            construction = {'case_id': case_id, 'cell_id': 'C183394',
                            'law_id': 'NRS-484D-215-1', 'actor': 'motor_vehicle_driver',
                            'entrypoint': 'runner.py', 'files': files,
                            'measurement_plan': '600 original 20 Hz frames; 1000-foot authored vehicle target, original actor range and pixel review decisive',
                            'recording_description': DESCRIPTION,
                            'status': 'authored_not_physically_verified'}
            target = ROOT / 'constructions' / case / candidate / 'construction.json'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(construction, indent=2, allow_nan=False) + '\n')
            print(case, candidate, hashlib.sha256(target.read_bytes()).hexdigest())


if __name__ == '__main__':
    build()
