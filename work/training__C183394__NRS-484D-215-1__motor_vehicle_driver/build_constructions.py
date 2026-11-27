"""Deterministically assemble exact inline beam constructions for CPU checking."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
SOURCE = ROOT / 'native'
CASES = ('condition_a', 'condition_b')
MODULES = ('runner.py', 'beam_capture.py', 'beam_native.py', 'beam_scene.py',
           'saved_beam.py', 'oncoming_beam.py', 'finalize.py')
CHANNELS = ('sig.headlamp', 'rel.oncoming', 'rel.centre_distance',
            'drv.approaching', 'drv.civil_night', 'env.civil_time',
            'st.roadway', 'st.shoulder', 'env.visibility')
DESCRIPTION = {'channels': [{'name': name, 'unit': 'structured',
    'sampling_rate_hz': 20, 'method': 'Original Native actor/lamp sample and source join',
    'time_window': 'entire original 30 s / 600-frame attempt',
    'reference_frame': 'original CARLA tick and four synchronized cameras',
    'uncertainty': '50 ms sample bracket; emitted glare and civil time need independent review'}
    for name in CHANNELS], 'context_inputs': [],
    'limitations': ['Original beam optics, driver-eye exposure and NRS 484D.100 timing require independent review']}


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for case in CASES:
    for candidate, gain in (('primary', .20), ('fallback1', .26)):
        case_id = AID + '__selected_6fb122bc__' + case
        config = {'selected_case_id': case_id,
                  'supported_case_ids': [AID + '__selected_6fb122bc__' + suffix for suffix in CASES],
                  'cell_id': 'C183394', 'law_id': 'NRS-484D-215-1',
                  'actor': 'motor_vehicle_driver', 'candidate_id': candidate,
                  'beam_mode': 'dim_within_500' if case == 'condition_a' else 'retain_high',
                  'rate_hz': 20, 'duration_s': 30, 'acceleration_gain': gain,
                  'requested_speed_mps': 2.5, 'required_atoms': [],
                  'source_packets': [],
                  'cameras': ['overview', 'approach', 'driver_reference', 'reference_corner'],
                  'case': {'recording_description': DESCRIPTION},
                  'recording_description': DESCRIPTION}
        test = '''import json
import unittest
from pathlib import Path
from runner import check
from beam_scene import beam_request

class Offline(unittest.TestCase):
    def test_exact_construction(self):
        value = check(Path(__file__).resolve().parents[1])
        self.assertEqual(value["frames"], 600)
        self.assertFalse(value["physical_success_claimed"])
        self.assertEqual(beam_request("dim_within_500", 152.4), "low_beam")
        self.assertEqual(beam_request("dim_within_500", 160.001), "high_beam")
'''
        files = [{'path': name, 'content': (SOURCE / name).read_text()} for name in MODULES]
        files += [{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
            {'path': 'tests/test_offline.py', 'content': test}]
        construction = {'case_id': case_id, 'cell_id': 'C183394',
                        'law_id': 'NRS-484D-215-1', 'actor': 'motor_vehicle_driver',
                        'entrypoint': 'runner.py', 'files': files,
                        'measurement_plan': '600 original 20 Hz frame joins, oncoming distance and lamp readback; no legal verdict',
                        'recording_description': config['recording_description'],
                        'status': 'authored_not_physically_verified'}
        target = ROOT / 'constructions' / case / candidate / 'construction.json'
        dump(target, construction)
        print(case, candidate, sha(target))
