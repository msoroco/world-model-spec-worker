import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exposure_case_setup import CASES, PREFIX
from exposure_comparison_audit import audit
from test_endangerment_measurement import sample


def write_saved(root, suffix):
    speed, kind, lateral = CASES[suffix]
    settings = {'case_id': PREFIX + suffix, 'speed_mps': speed,
                'exposed_kind': kind, 'outside_edge_m': lateral}
    config = {'selected_case_id': settings['case_id'], 'law_id': 'NRS-484B-600-1b',
              'cell_id': 'C136539', 'actor': 'motor_vehicle_driver',
              'rate_hz': 20, 'frames': 160, 'duration_s': 8,
              'requested_speed_mps': speed,
              'exposed_kind': kind, 'outside_edge_m': lateral,
              'construction_probe_only': True}
    root.mkdir()
    (root / 'config.json').write_text(json.dumps(config))
    (root / 'construction-probe.json').write_text(json.dumps({
        'case_id': settings['case_id'], 'exact_settings': settings,
        'map_name': 'fixture-map', 'road_id': 8, 'lane_id': -1}))
    (root / 'video_frames.jsonl').write_text(''.join(json.dumps({
        'video_frame': i, 'carla_frame': i, 'time_s': i * .05}) + '\n' for i in range(2)))
    (root / 'trace.jsonl').write_text(''.join(json.dumps({
        'frame': i, 'time_s': i * .05}) + '\n' for i in range(2)))
    rows = []
    for i in range(2):
        row = sample(i, 3)
        row['exposed_kind'] = kind
        rows.append(row)
    (root / 'exposed_actor_footprints.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))


class ComparisonAuditTests(unittest.TestCase):
    def test_all_four_pairs_and_fixed_conditions(self):
        pairs = [('speed_sweep_low_mid', 'slow_person_exposure', 'moderate_person_exposure'),
                 ('speed_sweep_mid_high', 'moderate_person_exposure', 'fast_person_exposure'),
                 ('pedestrian_clearance', 'moderate_person_exposure', 'clearance_reference'),
                 ('property_clearance', 'property_near', 'property_far')]
        for ident, a, b in pairs:
            with tempfile.TemporaryDirectory() as directory:
                left, right = Path(directory) / 'left', Path(directory) / 'right'
                write_saved(left, a); write_saved(right, b)
                result = audit(ident, left, right)
                self.assertFalse(result['physical_acceptance_claimed'])
                scene = json.loads((right / 'construction-probe.json').read_text())
                scene['lane_id'] = -2
                (right / 'construction-probe.json').write_text(json.dumps(scene))
                with self.assertRaisesRegex(ValueError, 'fixed road geometry changed'):
                    audit(ident, left, right)

    def test_missing_original_and_changed_kind_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            left, right = Path(directory) / 'left', Path(directory) / 'right'
            write_saved(left, 'property_near'); write_saved(right, 'property_far')
            rows = [json.loads(x) for x in (right / 'exposed_actor_footprints.jsonl').read_text().splitlines()]
            rows[1]['exposed_kind'] = 'pedestrian'
            (right / 'exposed_actor_footprints.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in rows))
            with self.assertRaisesRegex(ValueError, 'exposed kind differs'):
                audit('property_clearance', left, right)
            (right / 'exposed_actor_footprints.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                audit('property_clearance', left, right)
