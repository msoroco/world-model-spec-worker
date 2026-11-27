"""Assemble isolated exact 499/500/501-foot Native candidate constructions."""
import hashlib
import json
from pathlib import Path

from build_constructions import DESCRIPTION

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'native'
AID = ROOT.name
PROBES = ('distance_below_500ft', 'distance_at_500ft', 'distance_above_500ft')
MODULES = ('runner.py', 'beam_capture.py', 'beam_native.py', 'beam_scene.py',
           'probe_scene.py', 'saved_beam.py', 'oncoming_beam.py', 'finalize.py')


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def source(name):
    value = (SOURCE / name).read_text()
    if name in ('runner.py', 'beam_native.py'):
        value = value.replace('from beam_scene import ', 'from probe_scene import ')
    if name == 'beam_capture.py':
        value = value.replace('not case.endswith(\n            ("__condition_a", "__condition_b"))',
                              'case.rsplit("__", 1)[-1] not in ("distance_below_500ft", "distance_at_500ft", "distance_above_500ft")')
        value = value.replace('"condition_a" if case.endswith("__condition_a")\n                        else "condition_b"',
                              'case.rsplit("__", 1)[-1]')
        if 'case.rsplit("__", 1)[-1] not in' not in value or 'else "condition_b"' in value:
            raise ValueError('Probe capture substitution failed')
    return value


if __name__ == '__main__':
    ids = [AID+'__'+probe for probe in PROBES]
    for probe in PROBES:
        for candidate, gain in (('primary', .20), ('fallback1', .26)):
            case_id = AID+'__'+probe
            config = {'selected_case_id': case_id, 'supported_case_ids': ids,
                      'cell_id': 'C183394', 'law_id': 'NRS-484D-215-1',
                      'actor': 'motor_vehicle_driver', 'candidate_id': candidate,
                      'beam_mode': 'dim_within_500', 'rate_hz': 20, 'duration_s': 30,
                      'acceleration_gain': gain, 'requested_speed_mps': 2.5,
                      'required_atoms': [], 'source_packets': [],
                      'cameras': ['overview', 'approach', 'driver_reference', 'reference_corner'],
                      'case': {'recording_description': DESCRIPTION},
                      'recording_description': DESCRIPTION}
            test = '''import unittest
from pathlib import Path
from runner import check
from probe_scene import request, validate_request

class Offline(unittest.TestCase):
    def test_exact_probe(self):
        bundle = Path(__file__).resolve().parents[1]
        outcome = check(bundle)
        self.assertEqual(outcome['frames'], 600)
        self.assertFalse(outcome['physical_success_claimed'])
        suffix = outcome['case_id'].rsplit('__', 1)[-1]
        self.assertEqual(validate_request(request(suffix))['frames'], 600)
'''
            files = [{'path': name, 'content': source(name)} for name in MODULES]
            files.extend([{'path': 'config.json', 'content': json.dumps(config, indent=2)+'\n'},
                          {'path': 'tests/test_offline.py', 'content': test}])
            construction = {'case_id': case_id, 'cell_id': 'C183394',
                            'law_id': 'NRS-484D-215-1', 'actor': 'motor_vehicle_driver',
                            'entrypoint': 'runner.py', 'files': files,
                            'measurement_plan': '600 original 20 Hz frame joins; authored starting distance target, original actor readback controls',
                            'recording_description': DESCRIPTION,
                            'status': 'authored_not_physically_verified'}
            target = ROOT/'constructions'/probe/candidate/'construction.json'
            dump(target, construction)
            print(probe, candidate, hashlib.sha256(target.read_bytes()).hexdigest())
