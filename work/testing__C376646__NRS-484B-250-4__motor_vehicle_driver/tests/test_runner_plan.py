import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import native_inoperative_control
import inoperative_stop_measurements
import runner


class RunnerPlanTests(unittest.TestCase):
    def test_selected_stop_reference_and_hashed_site(self):
        config = json.loads((ROOT / 'config.json').read_text())
        receipt = runner.validate_capture_plan(config, ROOT)
        self.assertEqual(receipt['selected_boundary'], config['site']['stop_boundary']['kind'])
        self.assertFalse(receipt['native_site_verified'])
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory)
            for name in ('config.json', 'site-review.json', 'site-sources.json',
                         config['site']['native_map_xodr']['path']):
                (copy / name).write_bytes((ROOT / name).read_bytes())
            (copy / 'site-sources.json').write_text('changed source\n')
            with self.assertRaisesRegex(ValueError, 'source missing or changed'):
                runner.validate_capture_plan(config, copy)

    def test_uninventoried_native_signal_head_rejected(self):
        class Actors(list):
            def filter(self, pattern):
                return self

        class Light:
            def __init__(self, ident, road):
                self.id = ident
                self.road = road

            def get_affected_lane_waypoints(self):
                return [NS(road_id=self.road, lane_id=-1)]

        world = NS(get_actors=lambda: Actors([Light(1, 7), Light(2, 8), Light(3, 9)]))
        with self.assertRaisesRegex(ValueError, 'Uninventoried installed signal head'):
            native_inoperative_control.governing_lights(world, [[7, -1], [8, -1]])

    def test_selected_priority_controls_and_prohibited_stop(self):
        cases = ROOT / 'cases'
        inside = json.loads((ROOT / 'config.json').read_text())
        prior = json.loads((cases / 'crosswalk_other_previously_stopped' / 'config.json').read_text())
        no_halt = json.loads((cases / 'stop_line_no_halt' / 'config.json').read_text())
        self.assertEqual(inside['actor_routes']['ego']['release_rule'], 'after_partner_entry')
        self.assertEqual(prior['actor_routes']['ego']['release_rule'], 'after_other_clear')
        self.assertEqual(no_halt['actor_routes']['ego']['stop_policy'], 'rolling')
        self.assertEqual(runner.validate_capture_plan(no_halt, cases / 'stop_line_no_halt')['selected_boundary'], 'stop_line')

    def test_diagnostic_stop_outcomes_and_priority_basis(self):
        def analyze_source(suffix, clear_other=False):
            source = ROOT / 'cases' / suffix / (suffix + '-diagnostic-sources.json')
            files = json.loads(source.read_text())['files']
            with tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                for name in ('vehicle_signal_history.jsonl', 'junction_context.json', 'video_frames.jsonl'):
                    content = files[name]
                    if clear_other and name == 'vehicle_signal_history.jsonl':
                        rows = [json.loads(line) for line in content.splitlines()]
                        # Move the other body beyond the far edge at ego entry;
                        # its earlier full stop remains in the original rows.
                        rows[-1]['other']['body_vertices_xy_m'] = [[0.8, 11], [2.8, 11], [0.8, 13], [2.8, 13]]
                        content = ''.join(json.dumps(row) + '\n' for row in rows)
                    (folder / name).write_text(content)
                return inoperative_stop_measurements.analyze(folder)

        inside = analyze_source('stop_line_other_inside')
        no_halt = analyze_source('stop_line_no_halt')
        self.assertTrue(inside['ego_stopped_before_entry_observed'])
        self.assertTrue(inside['other_body_inside_at_ego_entry_observed'])
        self.assertFalse(no_halt['ego_stopped_before_entry_observed'])
        self.assertIsNone(no_halt['first_full_halt_before_or_at_selected_boundary']['ego'])
        prior_only = analyze_source('crosswalk_other_previously_stopped', clear_other=True)
        self.assertTrue(prior_only['other_completed_stop_before_ego_observed'])
        self.assertFalse(prior_only['other_body_inside_at_ego_entry_observed'])


if __name__ == '__main__':
    unittest.main()
