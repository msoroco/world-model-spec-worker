"""Focused positive and missing-source checks for freight saved measurements."""
import copy
from datetime import datetime, timedelta
import unittest
from pathlib import Path

from freight_plan import PREFIX, PURPOSES, check_request, measure_saved


HERE = Path(__file__).resolve().parent
ROAD = (HERE / 'yellow-freight-road.xodr').read_text()
CAMERAS = [{'name': name, 'fps': 20, 'width': 1280, 'height': 720,
            'fov_deg': 80, 'pose_strategy': 'source-bound reference'}
           for name in ('overview', 'approach', 'reference_corner', 'driver_reference')]
TAXI = [[4, 8, 0], [6, 8, 0], [4, 12, 0], [6, 12, 0],
        [4, 8, 2], [6, 8, 2], [4, 12, 2], [6, 12, 2]]


def config(suffix):
    case = PREFIX + suffix
    return {'case_id': case, 'selected_case_id': case,
            'assignment_id': PREFIX[:-2], 'law_id': 'LVMC-11-52-030-B',
            'cell_id': 'C150173', 'actor': 'taxi_driver',
            'requested_purpose': PURPOSES[suffix], 'duration_s': 30,
            'rate_hz': 20, 'frames': 600,
            'civil_start_local': '2026-11-26T10:00:00',
            'commercial_classification': 'pending_original_review',
            'sign_source_status': 'authored_proposal_unverified',
            'legal_verdict': None, 'cameras': CAMERAS}


def rows(suffix):
    start = datetime(2026, 11, 26, 10)
    result = []
    for i in range(600):
        if suffix == 'freight_load':
            x = 8 - min(max(i - 150, 0), 150) / 50
        elif suffix == 'freight_unload':
            x = 5 + min(max(i - 150, 0), 150) / 50
        else:
            x = 8
        cargo = [[x + dx, 9 + dy, z] for dx, dy, z in
                 ((-.2, -.2, 0), (.2, -.2, 0), (-.2, .2, 0), (.2, .2, 0),
                  (-.2, -.2, .4), (.2, -.2, .4), (-.2, .2, .4), (.2, .2, .4))]
        result.append({'video_frame': i, 'time_s': (i + 1) / 20,
            'source_kind': 'synthetic_cpu_fixture',
            'observed_purpose': PURPOSES[suffix],
            'taxi_actor_id': 11, 'cargo_actor_id': 12,
            'civil_time_local': (start + timedelta(seconds=(i + 1) / 20)).isoformat(timespec='milliseconds'),
            'taxi_body_vertices_xyz_m': TAXI,
            'cargo_body_vertices_xyz_m': cargo,
            'cargo_transfer_motion_observed': 150 <= i < 300 and suffix != 'freight_wait'})
    return result


class FreightPlanTest(unittest.TestCase):
    def test_three_exact_source_shaped_variants(self):
        for suffix in PURPOSES:
            with self.subTest(suffix=suffix):
                self.assertEqual(check_request(config(suffix), ROAD)['frames'], 600)
                result = measure_saved(rows(suffix), config(suffix))
                self.assertEqual(result['frames'], 600)
                self.assertIsNone(result['legal_verdict'])
                if suffix == 'freight_wait':
                    self.assertEqual(result['cargo_transfer_motion_frames'], 0)
                    self.assertEqual(result['cargo_displacement_m'], 0)
                else:
                    self.assertGreater(result['cargo_transfer_motion_frames'], 0)
                    self.assertGreater(result['cargo_displacement_m'], 2)

    def test_missing_cargo_source_fails(self):
        bad = rows('freight_load')
        bad[300].pop('cargo_body_vertices_xyz_m')
        with self.assertRaisesRegex(ValueError, 'cargo body geometry missing'):
            measure_saved(bad, config('freight_load'))

    def test_missing_commercial_and_sign_authority_are_not_filled(self):
        for key in ('commercial_classification', 'sign_source_status'):
            bad = copy.deepcopy(config('freight_load'))
            bad.pop(key)
            with self.assertRaises(ValueError):
                check_request(bad, ROAD)

    def test_frame_and_civil_time_gaps_fail(self):
        for key in ('video_frame', 'civil_time_local'):
            bad = rows('freight_load')
            bad[240].pop(key)
            with self.assertRaises((ValueError, KeyError)):
                measure_saved(bad, config('freight_load'))


if __name__ == '__main__':
    unittest.main()
