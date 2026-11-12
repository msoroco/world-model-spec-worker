"""Check the selected ego-right comparison against Native side geometry."""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_pair import plan_pair
sys.path.insert(0, str(ROOT.parents[1]/'runtime'))
from scenario_pipeline.worker_exchange.candidate_constructions import validate as validate_candidates


class Map:
    name = 'TownX'

    def get_waypoint(self, location, project_to_road=False):
        if project_to_road is not False:
            raise AssertionError('Native waypoint projection would change the source route')
        inside = 10 <= location.x <= 20 and -5 <= location.y <= 5
        road = 2 if location.y < -6 else 1
        return NS(road_id=road, lane_id=-1, lane_type='Driving',
                  is_junction=inside, get_junction=lambda: NS(id=44))


def pose(values):
    return NS(location=NS(x=values[0], y=values[1]),
              rotation=NS(yaw=values[3]))


class RightCase(unittest.TestCase):
    def test_three_bound_fallbacks_change_distinct_engineering_causes(self):
        entry = next(row for row in json.loads((ROOT/'execution-manifest.json').read_text())['cases']
                     if row['case_id'] == ROOT.name+'__off_ego_right_near_time')
        self.assertEqual(validate_candidates(ROOT, entry, 'NRS-484B-250-2', 'C125697',
                                             required=True, require_alternate=True,
                                             candidate_count=4)['fallbacks'],
                         ['fallback1', 'fallback2', 'fallback3'])
        original = json.loads(next(item['content'] for item in
                                   json.loads((ROOT/entry['construction']).read_text())['files']
                                   if item['path'] == 'config.json'))
        for candidate in entry['candidates']:
            cfg = json.loads(next(item['content'] for item in
                                  json.loads((ROOT/candidate['construction']).read_text())['files']
                                  if item['path'] == 'config.json'))
            ident = candidate['id']
            if ident == 'fallback1':
                self.assertEqual(cfg['site']['ego_approach'][1], -14)
                self.assertEqual(cfg['site']['routes']['ego'][0][1], -14)
                cfg['site']['ego_approach'] = original['site']['ego_approach']
                cfg['site']['routes']['ego'][0] = original['site']['routes']['ego'][0]
            elif ident == 'fallback2':
                self.assertNotEqual(cfg['site']['cameras']['approach'], original['site']['cameras']['approach'])
                cfg['site']['cameras']['approach'] = original['site']['cameras']['approach']
            else:
                self.assertEqual(cfg['other_release_frame'], 24)
                cfg['other_release_frame'] = original['other_release_frame']
            cfg.pop('site_review')
            fixed = dict(original)
            fixed.pop('site_review')
            self.assertEqual(cfg, fixed)

    def test_constructed_comparison_is_reciprocally_ego_right(self):
        construction = json.loads((ROOT/'cases/off_ego_right_near_time/construction.json').read_text())
        files = {item['path']: item['content'] for item in construction['files']}
        config = json.loads(files['config.json'])
        site = config['site']
        transforms = {key: pose(site[key]) for key in ('ego_approach', 'ego_entry',
                                                       'other_approach', 'other_entry')}
        plan = plan_pair(Map(), site, transforms, config['other_approach_side'])
        self.assertEqual(config['selected_case_id'], ROOT.name+'__off_ego_right_near_time')
        self.assertEqual(plan['declared_approach_side'], 'left')
        self.assertGreater(plan['other_lateral_to_ego_m'], 1)
        self.assertNotEqual(plan['approaches']['ego']['road_id'],
                            plan['approaches']['other']['road_id'])
        self.assertIn("carla.TrafficLightState, 'left')", files['runner.py'])
        with self.assertRaisesRegex(ValueError, 'reciprocally on ego right'):
            plan_pair(Map(), site, transforms, 'right')

    def test_original_packet_and_bound_measurement_show_left_side(self):
        fixture = json.loads((ROOT/'cases/off_ego_right_near_time/diagnostic.json').read_text())
        rows = [json.loads(line) for line in fixture['files']['crossing_history.jsonl'].splitlines()]
        first = rows[0]
        ego_x = sum(p[0] for p in first['ego']['body_vertices_xy_m'])/4
        other_x = sum(p[0] for p in first['other']['body_vertices_xy_m'])/4
        self.assertEqual((ego_x, other_x), (15, 0))
        entry = next(row for row in json.loads((ROOT/'execution-manifest.json').read_text())['cases']
                     if row['case_id'] == ROOT.name+'__off_ego_right_near_time')
        receipt = json.loads((ROOT/entry['compatibility']['receipt']).read_text())
        side = receipt['measurement_examples']['relative_right_side']['value']
        timing = receipt['measurement_examples']['entry_timing']['value']
        self.assertIs(side['other_spatially_right_of_ego_approach'], False)
        self.assertEqual(side['signed_lateral_offset_m'], 15)
        self.assertEqual(timing['first_complete_body_entry']['ego']['frame'], 101)
        self.assertEqual(timing['first_complete_body_entry']['other']['frame'], 102)
        self.assertEqual(receipt['negative_removed'], 'crossing_history.jsonl')
