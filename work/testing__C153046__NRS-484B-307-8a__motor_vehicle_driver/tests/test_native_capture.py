import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_capture import capture
from test_native_setup import World
import test_red_left_measurement as fixture


class Adapter:
    native_attested = False

    def __init__(self, bad_frame=None):
        self.world = World()
        self.bad_frame = bad_frame
        self.frame = 0
        self.requests = []
        self.braked = False
        self.restored = False

    def transform_factory(self, xyz, rpy):
        return xyz, rpy

    def get_opendrive_bytes(self):
        return b'opendrive'

    def tick(self, actors):
        frame = self.frame
        self.frame += 1
        return {'frame': frame, 'time_s': frame * 0.05}

    def read_original_frame(self, frame, actors):
        return {'origin': 'native_world_snapshot',
                'frame': frame + (1 if frame == self.bad_frame else 0),
                'time_s': frame * 0.05, 'signal_actor_id': '7',
                'signal_state': 'steady_red_alone',
                'ego': {'lane_id': 'left', 'speed_m_s': 0.0,
                        'body_vertices_xy': [[5, 2], [7, 2], [7, 4], [5, 4]]},
                'directed_participants': []}

    def read_cameras(self, frame, actors):
        return {name: {'frame': frame, 'time_s': frame * 0.05,
                       'png': b'\x89PNG\r\n\x1a\nfixture'}
                for name in ('overview', 'approach', 'reference_corner', 'driver_reference')}

    def apply_request(self, request, actors):
        self.requests.append(request)

    def brake(self):
        self.braked = True

    def restore(self):
        self.restored = True


class CaptureTest(unittest.TestCase):
    write_packet = fixture.RedLeftMeasurementTest.write_packet

    def setUp(self):
        fixture.RedLeftMeasurementTest.setUp(self)
        self.packet['spawn_plan'] = {
            'ego': {'lane_id': 'left', 'location_xyz_m': [0, 3.5, 0],
                    'rotation_rpy_deg': [0, 0, 0], 'blueprint_id': 'vehicle.test',
                    'source_citation': 'fixture-map'},
            'pedestrians': [], 'other_traffic': []}
        self.write_packet()
        self.config = {'selected_case_id': 'case-a',
                       'case': {'draft_variables': {
                           'stop_request': 'complete_stop', 'approach_position': 'extreme_left',
                           'receiving_direction': 'one_way_left',
                           'conflict_response_request': 'no_conflict',
                           'signal_request': 'steady_red_alone'}}}

    def test_original_frame_capture_and_owned_cleanup(self):
        adapter = Adapter()
        destination = self.root / 'capture'
        receipt = capture(adapter, self.config, self.packet_path, destination)
        self.assertEqual(receipt['original_frames'], 900)
        self.assertTrue(receipt['diagnostic_fixture'])
        self.assertEqual(len((destination / 'history.jsonl').read_text().splitlines()), 900)
        self.assertEqual(len(adapter.requests), 900)
        self.assertTrue(adapter.braked and adapter.restored)
        self.assertTrue(all(actor.destroyed for actor in adapter.world.spawned))

    def test_wrong_original_frame_rejected_and_no_partial_delivery(self):
        adapter = Adapter(bad_frame=3)
        destination = self.root / 'capture'
        with self.assertRaisesRegex(ValueError, 'snapshot/frame join'):
            capture(adapter, self.config, self.packet_path, destination)
        self.assertFalse(destination.exists())
        self.assertTrue(adapter.braked and adapter.restored)
        self.assertTrue(all(actor.destroyed for actor in adapter.world.spawned))


if __name__ == '__main__':
    unittest.main()
