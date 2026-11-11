"""Synthetic rows exercise original assessment mechanics; no original claim."""
import importlib.util
import copy
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('c132497_finalizer',
    ROOT/'native/finalize_current.py')
FINAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FINAL)


def sample(lane=-2):
    raw, trace, frames = [], [], []
    for i in range(240):
        frame = 1000+i
        road = 20 if i < 30 else 21 if i < 210 else 22
        ego = {'center_native_xyz_m': [float(i), 0.0, 1.0],
               'velocity_native_xyz_mps': [5.0, 0.0, 0.0],
               'speed_mps': 5.0, 'yaw_deg': 0.0}
        raw.append({'frame': i, 'native_frame': frame, 'time_s': (i+1)/20,
                    'source_kind': 'synthetic_native_sample', 'ego': ego,
                    'observed_road_id': road, 'observed_lane_id': lane})
        trace.append({'frame': frame, 'position_m': ego['center_native_xyz_m'],
                      'velocity_mps': ego['velocity_native_xyz_mps'],
                      'speed_mps': 5.0, 'heading_deg': 0.0})
        frames.append({'carla_frame': frame})
    return raw, trace, frames


class PhysicalAssessmentMechanics(unittest.TestCase):
    def setUp(self):
        self.raw, self.trace, self.frames = sample()
        self.cfg = {'road_sha256': 'a'*64, 'case_id': 'reference',
                    'candidate_id': 'primary', 'requested_lane_id': -2}
        self.map_readback = {'road_sha256': 'a'*64}
        self.capture = {'case_id': 'reference', 'candidate_id': 'primary',
                        'error': None, 'observed_frames': 240}

    def assess(self):
        return FINAL.assess_original_motion(self.raw, self.trace, self.frames,
            self.cfg, self.map_readback, self.capture)

    def test_route_assessment_mechanics(self):
        result = self.assess()
        self.assertTrue(result['maneuver_completed'])
        self.assertEqual(result['physical_failure_flags'], [])
        self.assertFalse(result['physical_checks']['legal_verdict_claimed'])

    def test_no_exit_rejected(self):
        for row in self.raw[210:]: row['observed_road_id'] = 21
        self.assertFalse(self.assess()['maneuver_completed'])

    def test_wrong_lane_rejected(self):
        self.raw[209]['observed_lane_id'] = -1
        self.assertFalse(self.assess()['maneuver_completed'])

    def test_stale_trace_rejected(self):
        self.trace[50]['speed_mps'] = 9.0
        self.assertIn('trace differs', ' '.join(self.assess()['physical_failure_flags']))

    def test_map_mismatch_rejected(self):
        self.map_readback['road_sha256'] = 'b'*64
        self.assertFalse(self.assess()['setup_confirmed'])

    def test_capture_failure_rejected(self):
        self.capture['error'] = 'camera failed'
        self.assertFalse(self.assess()['maneuver_completed'])

    def test_pinned_progress_and_route_must_both_pass(self):
        route = self.assess()
        route['physical_checks']['sources'] = {'native-raw-actors.jsonl': 'a'*64}
        generic = {'physical_checks': {'maneuver': {
            'status': 'met', 'method': 'synthetic sampled progress check',
            'sources': {'trace.jsonl': 'b'*64}, 'details': {}}}}
        merged = FINAL.merge_physical_assessments(copy.deepcopy(generic), route)
        self.assertEqual(merged['maneuver']['status'], 'met')
        self.assertEqual(set(merged['maneuver']['sources']),
                         {'trace.jsonl', 'native-raw-actors.jsonl'})
        route['maneuver_completed'] = False
        self.assertEqual(FINAL.merge_physical_assessments(
            copy.deepcopy(generic), route)['maneuver']['status'], 'not_met')
        generic['physical_checks']['maneuver']['status'] = 'unverified'
        self.assertEqual(FINAL.merge_physical_assessments(
            copy.deepcopy(generic), route)['maneuver']['status'], 'unverified')


if __name__ == '__main__': unittest.main()
