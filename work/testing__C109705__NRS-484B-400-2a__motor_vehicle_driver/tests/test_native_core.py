"""Diagnostic CPU fixture for the source-bound Native Core publication path."""

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from native_capture import capture
from native_core import project
from test_native_capture import FakeAdapter, body, packet
from test_native_map import CASE


class CompleteDiagnosticAdapter(FakeAdapter):
    """Synthetic frame stream; never represents physical CARLA evidence."""

    native_attested = True

    def __init__(self):
        super().__init__()
        self.native_attested = True
        self.ego_actor = NS(id=7)
        self.record_path = None

    def start_recorder(self, path):
        self.record_path = Path(path)
        self.record_path.write_bytes(b'synthetic recorder fixture')

    def stop_recorder(self):
        return ' Create 7: vehicle.test at 0 0 0\n'

    def read_body(self, frame):
        ego = self.read_ego(frame)
        return {'frame': frame, 'road_id': ego['road_id'],
                'body_vertices_m': [[x, y, 0.] for x, y in body(-.7)],
                'velocity_mps': [1., 0., 0.],
                'velocity_source': 'original_trace_actor_get_velocity'}

    def read_participants(self, frame):
        physical = self.read_body(frame)
        return [{'actor_id': 7, 'blueprint': 'vehicle.test',
                 'body_vertices_m': physical['body_vertices_m'],
                 'velocity_mps': physical['velocity_mps'],
                 'speed_mps': 1.,
                 'heading_deg': math.degrees(self.read_ego(frame)['ego_heading_rad'])}]

    def read_control_inventory(self, frame):
        time_s = (frame - 100) * .05
        return {'frame': frame, 'time_s': time_s, 'devices': [],
                'control_actor_inventory': {
                    'frame': frame, 'time_s': time_s,
                    'method': 'World.get_actors', 'prefix': 'traffic.',
                    'actor_ids': [], 'complete': True}}

    def read_graph(self, frame):
        time_s = (frame - 100) * .05
        controls = self.read_control_inventory(frame)
        observed = {**controls, 'participants': self.read_participants(frame)}
        return json.dumps({'format': 'native-adapter-graph-v1',
                           'multigraph': False,
                           'metadata': {'frame': frame,
                                        'simulation_time_s': time_s,
                                        'observed_evidence': observed},
                           'nodes': [{'id': 'ego', 'attributes': {
                               'actor_id': 7, 'carla_id': 7,
                               'sem_class': 'vehicle.test'}}],
                           'edges': []}, separators=(',', ':')).encode()

    def read_road_geometry(self):
        return {'source': 'diagnostic fixture'}


class NativeCoreTests(unittest.TestCase):
    def test_source_bound_diagnostic_core_and_media_positive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'survey.json'
            packet(survey)
            original = root / 'original'
            capture(CompleteDiagnosticAdapter(), CASE, survey, original)
            self.assertTrue(json.loads((original / 'acquisition.json').read_text())
                            ['diagnostic_fixture'])
            with self.assertRaisesRegex(ValueError, 'diagnostic original Native'):
                project(original, root / 'forbidden',
                        dimensions={name: (2, 2) for name in
                                    ('overview', 'approach', 'reference_corner',
                                     'driver_reference')})
            output = root / 'core'
            receipt = project(original, output, allow_diagnostic=True,
                              dimensions={name: (2, 2) for name in
                                          ('overview', 'approach', 'reference_corner',
                                           'driver_reference')})
            self.assertTrue(receipt['diagnostic_fixture'])
            self.assertEqual(receipt['frames'], 900)
            self.assertEqual(receipt['media']['frames'], 900)
            self.assertEqual(len((output / 'trace.jsonl').read_text().splitlines()), 900)
            self.assertEqual(len((output / 'capture/evidence.jsonl').read_text().splitlines()), 900)
            event = json.loads((output / 'capture/evidence.jsonl').read_text().splitlines()[0])
            self.assertEqual(event['ego']['speed_provenance'],
                             'original_trace_actor_get_velocity')
            self.assertEqual(event['original_observations']['control_actor_inventory']
                             ['method'], 'World.get_actors')
            self.assertTrue(all((output / (name + '.mkv')).is_file() for name in
                                ('overview', 'approach', 'reference_corner',
                                 'driver_reference')))
            self.assertFalse(json.loads((output / 'capture/manifest.json').read_text())
                             ['physical_completion'])


if __name__ == '__main__':
    unittest.main()
