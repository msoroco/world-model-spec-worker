import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import officer_capture_sequence as SEQUENCE
import officer_source_intake as INTAKE
import officer_traffic_sampler as TRAFFIC
from officer_camera import CAMERAS
from officer_camera_media import CameraMedia
from officer_site import SITE


CASE = 'testing__C157964__NRS-484B-257-2__motor_vehicle_driver__officer_controls_go'


def source_packet(root):
    sources = {}
    for name in ('road', 'sign_inventory', 'officer_authority', 'officer_control',
                 'other_route', 'camera_sight_review'):
        path = root / (name + ('.xodr' if name == 'road' else '.txt'))
        path.write_text(SITE.read_text() if name == 'road' else 'CPU fixture ' + name)
        sources[name] = {'path': path.name,
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    packet = {'format': 'worker-officer-subsection-2-source-review',
              'site_id': 'CPU-fixture-site', 'sources': sources,
              'review': {'site_id': 'CPU-fixture-site', 'non_through_highway': True,
                         'ego_entrance_id': 'ego', 'other_entrance_id': 'other',
                         'entrances': [{'entrance_id': 'ego', 'device': 'stop',
                                        'sign_visible': True},
                                       {'entrance_id': 'other', 'device': 'none',
                                        'sign_visible': True}],
                         'officer_authority_reviewed': True,
                         'officer_control_reviewed': True,
                         'original_camera_sight_reviewed': True,
                         'intersection_polygon_xy_m': [[-5, -5], [5, -5],
                                                        [5, 5], [-5, 5]]}}
    path = root / 'packet.json'
    path.write_text(json.dumps(packet))
    return path


class OfficerCaptureSequenceTests(unittest.TestCase):
    def native(self):
        state = {'frame': 40, 'controls': []}

        def tick():
            state['frame'] += 1
            return state['frame']

        world = NS(get_settings=lambda: NS(synchronous_mode=True,
                                            fixed_delta_seconds=0.05), tick=tick,
                   get_snapshot=lambda: NS(frame=state['frame'],
                                           timestamp=NS(elapsed_seconds=state['frame'] * 0.05)))
        vertices = [NS(x=0.0, y=0.0), NS(x=1.0, y=0.0),
                    NS(x=1.0, y=1.0), NS(x=0.0, y=1.0)]
        box = NS(get_world_vertices=lambda transform: vertices)
        ego = NS(id=11, get_velocity=lambda: NS(x=0.0, y=0.0, z=0.0),
                 get_transform=lambda: NS(), bounding_box=box,
                 apply_control=lambda value: state['controls'].append(value))
        other = NS(id=33, get_velocity=lambda: NS(x=0.0, y=0.0, z=0.0),
                   get_transform=lambda: NS(), bounding_box=box)
        officer = NS(id=12)
        carla = NS(VehicleControl=lambda **values: NS(**values))
        bone = lambda actor, direction: {'officer_actor_id': actor.id,
                                         'direction': direction,
                                         'realized_bones': {'arm': {'yaw': 10.0}}}
        traffic = lambda index: {'source': f'other-history#frame-{index}',
                                 'other_inside': True, 'approaching_hazard': False,
                                 'site_id': 'CPU-fixture-site', 'other_actor_id': 33,
                                 'other_body_vertices_xy_m': [[0, 0], [1, 0],
                                                              [1, 1], [0, 1]],
                                 'hazard_source': f'hazard-review#frame-{index}'}
        cameras = lambda frame: {name: {'carla_frame': frame,
                                        'raw_source': f'{name}.mkv#frame-{frame}'}
                                 for name in ('overview', 'approach', 'reference_corner',
                                              'driver_reference')}
        return carla, world, ego, officer, other, bone, traffic, cameras, state

    def test_full_fixture_sequence_and_text_receipt(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            packet = source_packet(root)
            carla, world, ego, officer, other, bone, traffic, cameras, state = self.native()
            intake = INTAKE.load_and_validate(root, packet)
            traffic = TRAFFIC.native_sampler(other, intake, lambda index: {
                'site_id': 'CPU-fixture-site', 'other_actor_id': 33,
                'approaching_hazard': False,
                'source': f'hazard-review.json#frame-{index}'})
            sensors = []

            def spawn(blueprint, transform, **kwargs):
                sensor = NS(callback=None,
                            listen=lambda callback: setattr(sensor, 'callback', callback),
                            stop=lambda: None, destroy=lambda: None)
                sensors.append(sensor)
                return sensor

            world.spawn_actor = spawn
            original_tick = world.tick

            def tick_with_cameras():
                frame = original_tick()
                for sensor in sensors:
                    sensor.callback(NS(frame=frame, width=4, height=4,
                                       raw_data=bytes([frame % 256, 0, 0, 255] * 16)))
                return frame

            world.tick = tick_with_cameras
            blueprints = {name: name + '-blueprint' for name in CAMERAS}
            mounts = {name: {'transform': name + '-mount', 'attach_to': None}
                      for name in CAMERAS}
            with CameraMedia(world, root / 'media', blueprints, mounts,
                             {'ego': ego, 'other': other, 'officer': officer},
                             sizes={name: (4, 4) for name in CAMERAS}) as media:
                result = SEQUENCE.run(carla, world, ego, officer, bone, CASE,
                                      frame_count=3, source_root=root, source_packet=packet,
                                      other_actor=other, traffic_sampler=traffic,
                                      camera_readback=media.readback)
            self.assertEqual([row['carla_frame'] for row in result['rows']], [41, 42, 43])
            self.assertEqual([row['officer_program']['programmed_direction']
                              for row in result['rows']], ['stop', 'go', 'go'])
            self.assertEqual(result['legal_exception_judgment'], 'unresolved')
            self.assertTrue(result['rows'][0]['traffic_source']['other_inside'])
            self.assertEqual(result['rows'][0]['traffic_source']['other_actor_id'], 33)
            self.assertEqual(result['rows'][0]['native_actor_source']['other']['actor_id'], 33)
            self.assertEqual(result['rows'][0]['native_actor_source']['frame'], 41)
            self.assertTrue(all((root / 'media' / (name + '.mkv')).is_file()
                                for name in CAMERAS))
            self.assertEqual([row['camera_raw_sources']['overview']['video_frame']
                              for row in result['rows']], [0, 1, 2])
            self.assertEqual(len(state['controls']), 3)
            receipt = SEQUENCE.write_receipt(result, root / 'capture-receipt.json')
            self.assertEqual(receipt['sha256'], hashlib.sha256(
                (root / 'capture-receipt.json').read_bytes()).hexdigest())

    def test_changed_source_and_wrong_settings_fail_before_tick(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            packet = source_packet(root)
            carla, world, ego, officer, other, bone, traffic, cameras, state = self.native()
            (root / 'road.xodr').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'Changed source file: road'):
                SEQUENCE.run(carla, world, ego, officer, bone, CASE,
                             frame_count=3, source_root=root, source_packet=packet,
                             other_actor=other, traffic_sampler=traffic,
                             camera_readback=cameras)
            self.assertEqual(state['frame'], 40)
            packet = source_packet(root)
            world.get_settings = lambda: NS(synchronous_mode=False,
                                            fixed_delta_seconds=0.05)
            with self.assertRaisesRegex(ValueError, '20 Hz synchronous'):
                SEQUENCE.run(carla, world, ego, officer, bone, CASE,
                             frame_count=3, source_root=root, source_packet=packet,
                             other_actor=other, traffic_sampler=traffic,
                             camera_readback=cameras)
            self.assertEqual(state['frame'], 40)

    def test_source_bound_but_invalid_site_rejected_before_tick(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            packet = source_packet(root)
            bad_site = (root / 'road.xodr').read_text().replace('type="205"',
                                                               'type="999"', 1)
            (root / 'road.xodr').write_text(bad_site)
            value = json.loads(packet.read_text())
            value['sources']['road']['sha256'] = hashlib.sha256(
                (root / 'road.xodr').read_bytes()).hexdigest()
            packet.write_text(json.dumps(value))
            carla, world, ego, officer, other, bone, traffic, cameras, state = self.native()
            with self.assertRaisesRegex(ValueError, 'signed ego entrance'):
                SEQUENCE.run(carla, world, ego, officer, bone, CASE,
                             frame_count=3, source_root=root, source_packet=packet,
                             other_actor=other, traffic_sampler=traffic,
                             camera_readback=cameras)
            self.assertEqual(state['frame'], 40)

    def test_duplicate_native_frame_and_incomplete_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            packet = source_packet(root)
            carla, world, ego, officer, other, bone, traffic, cameras, _ = self.native()
            world.tick = lambda: 41
            world.get_snapshot = lambda: NS(frame=41,
                                            timestamp=NS(elapsed_seconds=2.05))
            with self.assertRaisesRegex(ValueError, 'not strictly increasing'):
                SEQUENCE.run(carla, world, ego, officer, bone, CASE,
                             frame_count=3, source_root=root, source_packet=packet,
                             other_actor=other, traffic_sampler=traffic,
                             camera_readback=cameras)
            with self.assertRaisesRegex(ValueError, 'Incomplete Native capture rows'):
                SEQUENCE.write_receipt({'format': 'worker-officer-subsection-2-native-capture',
                                        'frame_count': 3, 'rows': []}, root / 'bad.json')

    def test_stale_snapshot_and_missing_actor_body_rejected(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            packet = source_packet(root)
            carla, world, ego, officer, other, bone, traffic, cameras, _ = self.native()
            world.get_snapshot = lambda: NS(frame=0,
                                            timestamp=NS(elapsed_seconds=0.0))
            with self.assertRaisesRegex(ValueError, 'Native snapshot differs'):
                SEQUENCE.run(carla, world, ego, officer, bone, CASE,
                             frame_count=3, source_root=root, source_packet=packet,
                             other_actor=other, traffic_sampler=traffic,
                             camera_readback=cameras)
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            packet = source_packet(root)
            carla, world, ego, officer, other, bone, traffic, cameras, _ = self.native()
            ego.bounding_box.get_world_vertices = lambda transform: []
            with self.assertRaisesRegex(ValueError, 'Complete Native ego body'):
                SEQUENCE.run(carla, world, ego, officer, bone, CASE,
                             frame_count=3, source_root=root, source_packet=packet,
                             other_actor=other, traffic_sampler=traffic,
                             camera_readback=cameras)
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            packet = source_packet(root)
            carla, world, ego, officer, other, bone, traffic, cameras, state = self.native()
            world.get_snapshot = lambda: NS(frame=state['frame'],
                                            timestamp=NS(elapsed_seconds=1.0))
            with self.assertRaisesRegex(ValueError, 'time not strictly increasing'):
                SEQUENCE.run(carla, world, ego, officer, bone, CASE,
                             frame_count=3, source_root=root, source_packet=packet,
                             other_actor=other, traffic_sampler=traffic,
                             camera_readback=cameras)


if __name__ == '__main__':
    unittest.main()
