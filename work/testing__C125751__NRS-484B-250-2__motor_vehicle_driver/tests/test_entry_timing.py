import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from entry_timing import ASSIGNMENT, measure, measure_sealed


def survey():
    return {'cell_id': 'C125751', 'crossing_kind': 'median_opening_roadway_crossing',
            'crossing_bounds_xy_m': [-2, -2, 2, 2], 'opendrive_sha256': 'a' * 64,
            'approach_road_ids': {'ego': 1, 'other': 2},
            'public_highway_source': 'reviewed original road inventory',
            'governing_device': 'official_traffic_light',
            'ego_direction_xy': [0, 1], 'ego_approach_xy': [0, -10],
            'other_approach_xy': [10, 0]}


def body(x, y):
    return [[x-.2, y-.2], [x+.2, y-.2], [x+.2, y+.2], [x-.2, y+.2]]


def trace(case='precedence', ego_entry=66, other_entry=60):
    rows = []
    for i in range(900):
        ego_y = -10 if i < ego_entry else 0 if i < ego_entry+10 else 10
        other_x = 10 if i < other_entry else 0 if i < other_entry+10 else -10
        rows.append({'frame': i, 'time_s': i/20, 'native_frame_id': 1000+i,
                     'native_elapsed_seconds': 50+i/20,
                     'governing_device_readback': 'inoperative',
                     'ego': {'id': 10, 'road_id': 1, 'body_vertices_xy_m': body(0, ego_y)},
                     'other': {'id': 11, 'road_id': 2, 'body_vertices_xy_m': body(other_x, 0)}})
    return {'case_id': ASSIGNMENT+'__'+case, 'map_sha256': 'a'*64,
            'actor_ids': {'ego': 10, 'other': 11}, 'frames': rows}


class EntryTimingTests(unittest.TestCase):
    def test_exact_probe_cases_and_comparison_isolation(self):
        plan = json.loads((ROOT / 'case-plan.json').read_text())
        probe = json.loads((ROOT / 'judgment-probe-plan.json').read_text())['ranges'][0]
        rows = {row['case_id'].removeprefix(ASSIGNMENT+'__'): row for row in plan['cases']}
        self.assertEqual(set(rows), {'precedence', 'advance', 'timing_below',
                                     'timing_inside', 'timing_above'})
        for band in ('below', 'inside', 'above'):
            self.assertEqual(rows['timing_'+band]['requested_entry_difference_s'],
                             probe['planning_targets'][band])
        self.assertEqual(rows['precedence']['requested_entry_difference_s'],
                         rows['advance']['requested_entry_difference_s'])
        self.assertEqual(rows['timing_below']['requested_ego_response'],
                         rows['timing_above']['requested_ego_response'])
        self.assertEqual(len(plan['comparisons']), 2)

    def test_all_diagnostic_construction_hashes_and_targets(self):
        manifest = json.loads((ROOT/'execution-manifest.draft.json').read_text())
        plan = json.loads((ROOT/'case-plan.json').read_text())
        planned = {row['case_id']: row for row in plan['cases']}
        self.assertEqual({row['case_id'] for row in manifest['cases']}, set(planned))
        for row in manifest['cases']:
            path = ROOT/row['construction']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                             row['construction_sha256'])
            package = json.loads(path.read_text())
            files = {item['path']: item['content'] for item in package['files']}
            config = json.loads(files['config.json'])
            self.assertEqual(config['requested_entry_difference_s'],
                             planned[row['case_id']]['requested_entry_difference_s'])
            self.assertFalse(package['diagnostic_only'])

    def test_original_entry_brackets_right_side_and_unresolved_law(self):
        result = measure(trace(), survey())
        self.assertEqual(result['entry_brackets']['ego']['native_frame_id'], 1066)
        self.assertAlmostEqual(result['entry_brackets']['ego']['lower_elapsed_seconds'], 53.25)
        self.assertAlmostEqual(result['ego_minus_other_upper_entry_s'], .3)
        self.assertEqual(result['other_approach_side_of_ego'], 'right')
        self.assertEqual(result['governing_device_entry_states'],
                         {'ego':'inoperative','other':'inoperative'})
        self.assertEqual(result['statutory_applicability'],
                         'unresolved_official_device_exclusion_and_subsection_4')
        self.assertEqual(result['right_of_way_judgment'], 'unresolved')

    def test_original_signal_state_is_bound_to_each_entry_frame(self):
        packet=trace()
        packet['frames'][60]['governing_device_readback']='green'
        packet['frames'][66]['governing_device_readback']='red'
        result=measure(packet,survey())
        self.assertEqual(result['governing_device_entry_states'],
                         {'ego':'red','other':'green'})
        self.assertEqual(result['statutory_applicability'],
                         'unresolved_official_device_exclusion_and_subsection_4')

    def test_clock_footprint_and_device_negative_branches(self):
        for mutation, message in (
            (lambda t: t['frames'][30].update(native_frame_id=2000), 'clock discontinuity'),
            (lambda t: t['frames'][30].update(governing_device_readback=None), 'device readback'),
            (lambda t: t['frames'][0]['ego'].update(body_vertices_xy_m=body(0, 0)), 'outside crossing'),
            (lambda t: t['frames'][30]['other'].update(id=10), 'actor or approach road')):
            packet = trace()
            mutation(packet)
            with self.assertRaisesRegex(ValueError, message):
                measure(packet, survey())

    def test_source_seal_and_changed_packet_rejected(self):
        scratch = Path(__file__).resolve().parents[3] / '.runtime-work' / 'c125751-entry-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            survey_path = root / 'survey.json'
            survey_path.write_text(json.dumps(survey())+'\n')
            trace_path = root / 'original-trace.json'
            trace_path.write_text(json.dumps(trace())+'\n')
            manifest_path = root / 'source-manifest.json'
            manifest = {'survey_sha256': hashlib.sha256(survey_path.read_bytes()).hexdigest(),
                        'trace': {'path': trace_path.name,
                                  'sha256': hashlib.sha256(trace_path.read_bytes()).hexdigest()}}
            manifest_path.write_text(json.dumps(manifest)+'\n')
            self.assertAlmostEqual(measure_sealed(root, manifest_path, survey_path)
                                   ['ego_minus_other_upper_entry_s'], .3)
            trace_path.write_text(trace_path.read_text().replace('inoperative', 'green', 1))
            with self.assertRaisesRegex(ValueError, 'digest differs'):
                measure_sealed(root, manifest_path, survey_path)


if __name__ == '__main__':
    unittest.main()
