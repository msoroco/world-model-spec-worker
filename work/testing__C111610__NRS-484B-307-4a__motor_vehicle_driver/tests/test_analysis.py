import hashlib
import json
import sys
import shutil
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import build_report, measure, saved_result
from comparison_audit import audit, audit_traffic


def body(x, y):
    return [[x, y, 0], [x + 1, y, 0], [x + 1, y + 1, 0], [x, y + 1, 0]]


def row(frame, x, y, speed, brake, person=False):
    return {'frame': frame, 'time_s': frame / 20,
            'facing_signal': {'source_verified': True, 'source_ref': 'Native facing head 7',
                'head_id': 7, 'observed_frame': frame,
                'illuminated_indications': [{'color': 'green', 'shape': 'arrow', 'direction': 'left'}]},
            'ego': {'source_ref': 'Native ego', 'heading_source': 'Native transform',
                    'heading_deg': 90 if y > 0 else 0,
                    'body_vertices_m': body(x, y), 'speed_mps': speed, 'brake': brake},
            'pedestrians': ([{'id': 'p1', 'role': 'pedestrian', 'source_ref': 'Native walker',
                'lawful_presence_source': 'pedestrian-entry.jsonl and original Walk head',
                'lawfully_present': True, 'body_vertices_m': body(0, 5)}] if person else []),
            'other_traffic': []}


def fixture(path, occupied, traffic_case=False):
    scene = json.loads((ROOT / 'scene.json').read_text())
    rows = [row(1, -7, -1.75, 0, 1, occupied),
            row(2, -7, -1.75, 0, 1, occupied),
            row(3, -5, 0, 2, 0), row(4, 0, 4, 2, 0)]
    if traffic_case:
        for index in (0, 1):
            rows[index]['other_traffic'] = [{'id': 'car-2', 'role': 'motor_vehicle',
                'source_ref': 'Native other vehicle',
                'lawful_presence_source': 'traffic-entry.jsonl and original green head',
                'lawfully_using_intersection': True,
                'body_vertices_m': body(0, index)}]
    context = {'map_source': 'Native map', 'adjacent_crosswalk_source': 'Native map marking',
               'ego_route_source': 'Native waypoints', 'facing_head_source': 'Native signal',
               'lawful_presence_method': 'Native phase and geometry', 'facing_head_id': 7,
               'adjacent_crosswalk_bounds_m': scene['adjacent_crosswalk_bounds_m'],
               'route_waypoints': [{'x_m': x, 'y_m': y, 'road_id': 1, 'lane_id': 1}
                                   for x, y in [(-20, -1.75), (-4, -1.75), (0, 0), (0, 20)]],
               'crosswalk_vertices_m': [[-2, 4], [2, 4], [2, 8], [-2, 8]],
               'camera_profile': 'overview1080-capability', 'duration_s': .2}
    context['pedestrian_entry_source'] = 'pedestrian-entry.jsonl' if occupied else None
    context['other_vehicle_entry_source'] = 'traffic-entry.jsonl' if traffic_case else None
    if traffic_case:
        context['other_vehicle_signal_head_id'] = 9
        context['other_vehicle_route_waypoints'] = [
            {'x_m': 0, 'y_m': y, 'road_id': 2, 'lane_id': 1} for y in (-12, 0, 10)]
    sources = {'turn-history.jsonl': ''.join(json.dumps(r) + '\n' for r in rows),
               'video_frames.jsonl': ''.join(json.dumps({'video_frame': index,
                   'carla_frame': r['frame'], 'time_s': r['time_s']}) + '\n'
                   for index, r in enumerate(rows)),
               'intersection-context.json': json.dumps(context) + '\n'}
    if occupied:
        entry = [{'frame': frame, 'time_s': frame / 20,
                  'pedestrian_signal_head_id': 8, 'walk_state': 'Walk',
                  'person_body_vertices_m': body(x, 5)}
                 for frame, x in [(-2, -2), (-1, -1), (0, 0)]]
        sources['pedestrian-entry.jsonl'] = ''.join(json.dumps(r) + '\n' for r in entry)
    if traffic_case:
        entry = [{'frame': frame, 'time_s': frame / 20,
                  'other_vehicle_signal_head_id': 9, 'green_state': 'Green',
                  'vehicle_body_vertices_m': body(0, y),
                  'route_source': 'Native CARLA connected waypoints'}
                 for frame, y in [(-2, -2), (-1, -1), (0, 0)]]
        sources['traffic-entry.jsonl'] = ''.join(json.dumps(r) + '\n' for r in entry)
    acquisition = {}
    for name, content in sources.items():
        (path / name).write_text(content)
        acquisition[name] = {'kind': 'original_native',
                             'sha256': hashlib.sha256(content.encode()).hexdigest()}
    (path / 'acquisition.json').write_text(json.dumps(acquisition))
    folder = (ROOT / 'cases/crosswalk_occupied_yield' if occupied else
              ROOT / 'cases/lawful_traffic_yield' if traffic_case else ROOT)
    for name in ('scene.json', 'config.json', 'construction.json'):
        shutil.copyfile(folder / name, path / name)
    for name in ('scene.json', 'config.json'):
        item = path / name
        value = json.loads(item.read_text())
        value['duration_s'] = .2
        item.write_text(json.dumps(value) + '\n')
    return rows


class SavedArrowTests(unittest.TestCase):
    def test_other_traffic_comparison_preserves_fixed_conditions(self):
        with tempfile.TemporaryDirectory() as clear_dir, tempfile.TemporaryDirectory() as traffic_dir:
            clear, traffic = Path(clear_dir), Path(traffic_dir)
            fixture(clear, False)
            fixture(traffic, False, traffic_case=True)
            self.assertEqual(audit_traffic(clear, traffic)['status'], 'passed')
            context_path = traffic / 'intersection-context.json'
            context = json.loads(context_path.read_text())
            context['camera_profile'] = 'changed'
            context_path.write_text(json.dumps(context))
            acquisition = json.loads((traffic / 'acquisition.json').read_text())
            acquisition['intersection-context.json']['sha256'] = hashlib.sha256(context_path.read_bytes()).hexdigest()
            (traffic / 'acquisition.json').write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, 'camera profile|fixed condition'):
                audit_traffic(clear, traffic)

    def test_lawful_other_traffic_yield_and_green_entry_required(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            fixture(path, False, traffic_case=True)
            report = measure(path, 'lawful_traffic_yield')
            self.assertEqual(report['traffic_frames'], [1, 2])
            self.assertEqual(report['traffic_yield_hold_frames'], [1, 2])
            self.assertEqual(report['legal_right_of_way_verdict'], 'unresolved')
            entry_path = path / 'traffic-entry.jsonl'
            entry = [json.loads(line) for line in entry_path.read_text().splitlines()]
            entry[0]['green_state'] = 'Red'
            entry_path.write_text(''.join(json.dumps(row) + '\n' for row in entry))
            acquisition = json.loads((path / 'acquisition.json').read_text())
            acquisition['traffic-entry.jsonl']['sha256'] = hashlib.sha256(entry_path.read_bytes()).hexdigest()
            (path / 'acquisition.json').write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, 'lawful green entry'):
                measure(path, 'lawful_traffic_yield')

    def test_clear_and_occupied_positive(self):
        for occupied in (False, True):
            with self.subTest(occupied=occupied), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                fixture(path, occupied)
                report = measure(path, 'crosswalk_occupied_yield' if occupied else 'crosswalk_clear_turn')
                self.assertEqual(report['frame_count'], 4)
                self.assertEqual(bool(report['lawful_occupancy_frames']), occupied)
                self.assertEqual(report['legal_right_of_way_verdict'], 'unresolved')
                saved = build_report(path)
                self.assertTrue(saved['analysis_complete'])
                self.assertEqual(saved['measurements']['adjacent_crosswalk_yield_measurement']['value']['frame_count'], 4)

    def test_saved_finalizer_projects_only_declared_original_channels(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            fixture(path, True)
            report = build_report(path)
            module = types.ModuleType('worker_exchange.native_output')
            module.physical_result = lambda _attempt, result: dict(result,
                physical_checks={'setup': {'status': 'unverified'}},
                realized_observables={})
            module.validate_result = lambda result: result
            package = types.ModuleType('worker_exchange')
            with patch.dict(sys.modules, {'worker_exchange': package,
                                          'worker_exchange.native_output': module}):
                result = saved_result(path, report)
            self.assertEqual(result['case_id'],
                'testing__C111610__NRS-484B-307-4a__motor_vehicle_driver__crosswalk_occupied_yield')
            channels = path / 'channels'
            self.assertTrue((channels / 'facing_arrow_history.jsonl').is_file())
            self.assertEqual(len((channels / 'camera_frame_map.jsonl').read_text().splitlines()), 4)
            self.assertFalse(result['setup_confirmed'])

    def test_stale_original_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            fixture(path, False)
            with (path / 'turn-history.jsonl').open('a') as stream:
                stream.write('{}\n')
            with self.assertRaisesRegex(ValueError, 'stale original'):
                measure(path, 'crosswalk_clear_turn')

    def test_missing_walk_entry_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            fixture(path, True)
            (path / 'pedestrian-entry.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                measure(path, 'crosswalk_occupied_yield')

    def test_arrow_and_yield_violation_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            rows = fixture(path, True)
            rows[0]['facing_signal']['head_id'] = 8
            self._replace_rows(path, rows)
            with self.assertRaisesRegex(ValueError, 'ego-facing'):
                measure(path, 'crosswalk_occupied_yield')
            rows[0]['facing_signal']['head_id'] = 7
            rows[1]['ego']['speed_mps'] = 2
            self._replace_rows(path, rows)
            with self.assertRaisesRegex(ValueError, 'did not hold'):
                measure(path, 'crosswalk_occupied_yield')

    def test_comparison_rechecks_original_sources_and_fixed_conditions(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            clear, occupied = Path(first), Path(second)
            fixture(clear, False)
            fixture(occupied, True)
            report = audit(clear, occupied)
            self.assertEqual(report['status'], 'passed')
            context_path = occupied / 'intersection-context.json'
            context = json.loads(context_path.read_text())
            context['camera_profile'] = 'changed-view'
            content = json.dumps(context) + '\n'
            context_path.write_text(content)
            acquisition = json.loads((occupied / 'acquisition.json').read_text())
            acquisition['intersection-context.json']['sha256'] = hashlib.sha256(content.encode()).hexdigest()
            (occupied / 'acquisition.json').write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, 'camera profile'):
                audit(clear, occupied)

    @staticmethod
    def _replace_rows(path, rows):
        content = ''.join(json.dumps(r) + '\n' for r in rows)
        (path / 'turn-history.jsonl').write_text(content)
        acquisition = json.loads((path / 'acquisition.json').read_text())
        acquisition['turn-history.jsonl']['sha256'] = hashlib.sha256(content.encode()).hexdigest()
        (path / 'acquisition.json').write_text(json.dumps(acquisition))
