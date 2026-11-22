import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import measure
from comparison_audit import audit

OCCUPIED = ROOT / 'cases/crosswalk_occupied_yield/scene.json'


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
                'lawful_presence_source': 'Native crosswalk phase and geometry',
                'lawfully_present': True, 'body_vertices_m': body(0, 5)}] if person else []),
            'other_traffic': []}


def fixture(path, occupied):
    scene = json.loads((ROOT / 'scene.json').read_text())
    rows = [row(1, -7, -1.75, 0, 1, occupied),
            row(2, -7, -1.75, 0, 1, occupied),
            row(3, -5, 0, 2, 0), row(4, 0, 4, 2, 0)]
    context = {'map_source': 'Native map', 'adjacent_crosswalk_source': 'Native map marking',
               'ego_route_source': 'Native waypoints', 'facing_head_source': 'Native signal',
               'lawful_presence_method': 'Native phase and geometry', 'facing_head_id': 7,
               'adjacent_crosswalk_bounds_m': scene['adjacent_crosswalk_bounds_m'],
               'route_waypoints': [[-20, -1.75], [-4, -1.75], [0, 0], [0, 20]],
               'crosswalk_vertices_m': [[-2, 4], [2, 4], [2, 8], [-2, 8]],
               'camera_profile': 'four-view-20Hz', 'duration_s': 30}
    sources = {'turn-history.jsonl': ''.join(json.dumps(r) + '\n' for r in rows),
               'video_frames.jsonl': ''.join(json.dumps({'frame': r['frame'], 'time_s': r['time_s']}) + '\n' for r in rows),
               'intersection-context.json': json.dumps(context) + '\n'}
    acquisition = {}
    for name, content in sources.items():
        (path / name).write_text(content)
        acquisition[name] = {'kind': 'original_native',
                             'sha256': hashlib.sha256(content.encode()).hexdigest()}
    (path / 'acquisition.json').write_text(json.dumps(acquisition))
    return rows


class SavedArrowTests(unittest.TestCase):
    def test_clear_and_occupied_positive(self):
        for occupied in (False, True):
            with self.subTest(occupied=occupied), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                fixture(path, occupied)
                report = measure(path, 'crosswalk_occupied_yield' if occupied else 'crosswalk_clear_turn',
                                 OCCUPIED if occupied else None)
                self.assertEqual(report['frame_count'], 4)
                self.assertEqual(bool(report['lawful_occupancy_frames']), occupied)
                self.assertEqual(report['legal_right_of_way_verdict'], 'unresolved')

    def test_stale_original_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            fixture(path, False)
            with (path / 'turn-history.jsonl').open('a') as stream:
                stream.write('{}\n')
            with self.assertRaisesRegex(ValueError, 'stale original'):
                measure(path, 'crosswalk_clear_turn')

    def test_arrow_and_yield_violation_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            rows = fixture(path, True)
            rows[0]['facing_signal']['head_id'] = 8
            self._replace_rows(path, rows)
            with self.assertRaisesRegex(ValueError, 'ego-facing'):
                measure(path, 'crosswalk_occupied_yield', OCCUPIED)
            rows[0]['facing_signal']['head_id'] = 7
            rows[1]['ego']['speed_mps'] = 2
            self._replace_rows(path, rows)
            with self.assertRaisesRegex(ValueError, 'did not hold'):
                measure(path, 'crosswalk_occupied_yield', OCCUPIED)

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
            with self.assertRaisesRegex(ValueError, 'camera_profile'):
                audit(clear, occupied)

    @staticmethod
    def _replace_rows(path, rows):
        content = ''.join(json.dumps(r) + '\n' for r in rows)
        (path / 'turn-history.jsonl').write_text(content)
        acquisition = json.loads((path / 'acquisition.json').read_text())
        acquisition['turn-history.jsonl']['sha256'] = hashlib.sha256(content.encode()).hexdigest()
        (path / 'acquisition.json').write_text(json.dumps(acquisition))
