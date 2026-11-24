import hashlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import native_capture as subject
import camera_recorder
import pixel_audit
import warning_audit
from emergency_scene import scene_geometry

CASE = subject.PREFIX + 'response_siren_pedestrian'


class Actor:
    def __init__(self): self.destroyed = False
    def set_autopilot(self, value): self.autopilot = value
    def destroy(self): self.destroyed = True


class World:
    def __init__(self):
        self.frame = 0
        self.actors = []
        self.map = types.SimpleNamespace(to_opendrive=lambda: 'fixture-map')
    def get_map(self): return self.map
    def get_blueprint_library(self):
        return types.SimpleNamespace(find=lambda key: types.SimpleNamespace(id=key))
    def try_spawn_actor(self, bp, transform):
        actor = Actor(); self.actors.append(actor); return actor
    def tick(self): self.frame += 1; return self.frame
    def get_snapshot(self):
        return types.SimpleNamespace(frame=self.frame,
            timestamp=types.SimpleNamespace(elapsed_seconds=self.frame / 20))


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.world = World()
        geometry = scene_geometry('eastbound')
        site = {'case_id': CASE, 'cell_id': 'C109035', 'actor': 'emergency_vehicle_driver',
            'reviewer': 'synthetic CPU test', 'source_citation': 'synthetic CPU test',
            'opendrive_sha256': hashlib.sha256(b'fixture-map').hexdigest(),
            'approach': 'eastbound', 'pedestrian_role': 'approach_warning_recipient',
            'ego_blueprint_id': 'vehicle.test', 'pedestrian_blueprint_id': 'walker.pedestrian.test',
            'ego_transform': {'location': [*geometry['ego_spawn_xy_m'], 0], 'rotation': [0, 0, 0]},
            'pedestrian_transform': {'location': [*geometry['pedestrian_spawn_xy_m'], 0], 'rotation': [0, 0, 0]}}
        self.site = self.folder / 'site.json'; self.site.write_text(json.dumps(site))
        dispatch = {'case_id': CASE, 'source_kind': 'dispatch_context', 'reviewer': 'synthetic CPU test',
                    'source_citation': 'synthetic CPU test', 'source_status': 'documented',
                    'event': 'emergency_call', 'event_interval_frames': [100, 500]}
        equipment = {'case_id': CASE, 'source_kind': 'equipment_record', 'reviewer': 'synthetic CPU test',
                     'source_citation': 'synthetic CPU test', 'authorization_source': 'test',
                     'device_installation_source': 'test', 'audibility_500ft_status': 'unknown'}
        self.dispatch = self.folder / 'dispatch.json'; self.dispatch.write_text(json.dumps(dispatch))
        self.equipment = self.folder / 'equipment.json'; self.equipment.write_text(json.dumps(equipment))
        self.commands = []
        self.api = types.SimpleNamespace(Location=lambda *x: x, Rotation=lambda *x: x,
                                         Transform=lambda a, b: (a,b))
    def tearDown(self): self.temp.cleanup()
    def run_capture(self, **overrides):
        args = {'world': self.world, 'carla_api': self.api, 'case_id': CASE,
                'site_packet': self.site, 'dispatch_document': self.dispatch,
                'equipment_document': self.equipment, 'output': self.folder / 'out',
                'device_command': lambda ego, *, siren, lamps: self.commands.append((siren, lamps)),
                'device_readback': lambda ego: {'siren_active': self.commands[-1][0],
                    'warning_lamp_active': self.commands[-1][1], 'source_type': 'instrument_test',
                    'source_citation': 'synthetic CPU test'},
                'drive_step': lambda ego, pedestrian, tick: None,
                'camera_capture': lambda frame: {key: f'test-{key}-{frame}' for key in ('front','rear','left','right')}}
        args.update(overrides)
        return subject.capture(**args)
    def test_full_source_seal_and_distinct_command_readback(self):
        receipt = self.run_capture()
        self.assertEqual(receipt['native_last_frame'], 900)
        self.assertFalse(receipt['physical_acceptance_claimed'])
        lines = [json.loads(x) for x in (self.folder/'out/device_trace.jsonl').read_text().splitlines()]
        self.assertEqual(len(lines), 900)
        self.assertFalse(lines[0]['siren_active'])
        self.assertTrue(lines[160]['siren_active'])
        self.assertFalse(self.commands[-1][0])
        self.assertTrue(all(a.destroyed for a in self.world.actors))
        for source in receipt['sources'].values():
            self.assertEqual(hashlib.sha256((self.folder/'out'/source['path']).read_bytes()).hexdigest(), source['sha256'])
        observed = warning_audit.audit(self.folder/'out', receipt)
        self.assertEqual(observed['observed_siren_frames'], 281)
        self.assertTrue(observed['all_siren_frames_within_documented_event'])
        camera_ref = receipt['sources']['camera_trace']
        camera_path = self.folder/'out'/camera_ref['path']
        rows = camera_path.read_text().splitlines()
        rows[2] = json.dumps({'frame': 2, 'native_frame': 99, 'sources': {'front': 'bad'}})
        changed = '\n'.join(rows) + '\n'
        camera_path.write_text(changed)
        receipt['sources']['camera_trace']['sha256'] = hashlib.sha256(changed.encode()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'synchronization mismatch'):
            warning_audit.audit(self.folder/'out', receipt)
    def test_command_echo_source_rejected_and_cleanup(self):
        with self.assertRaisesRegex(ValueError, 'Independent device-state source'):
            self.run_capture(device_readback=lambda ego: {'siren_active': False,
                'warning_lamp_active': False, 'source_type': 'command_echo', 'source_citation': 'test'})
        self.assertTrue(all(a.destroyed for a in self.world.actors))
        self.assertEqual(self.commands[-1], (False, False))
    def test_camera_gap_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Four synchronized camera'):
            self.run_capture(camera_capture=lambda frame: {'front': 'only'})
        self.assertTrue(all(a.destroyed for a in self.world.actors))
    def test_undocumented_dispatch_rejected_before_spawn(self):
        doc = json.loads(self.dispatch.read_text()); doc.pop('source_citation')
        self.dispatch.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError, 'review missing'):
            self.run_capture()
        self.assertFalse(self.world.actors)

    def test_original_camera_recorder_seals_and_decodes_3600_pixels(self):
        image = types.SimpleNamespace(width=2, height=2,
                                      raw_data=bytes([3, 2, 1, 255] * 4))
        def read(frame):
            image.frame = frame
            return {key: image for key in camera_recorder.CAMERAS}
        recorder = camera_recorder.CameraRecorder(
            self.folder / 'out', read, case_id=CASE,
            source_ids={key: 'synthetic-sensor-' + key for key in camera_recorder.CAMERAS},
            sizes={key: (2, 2) for key in camera_recorder.CAMERAS})
        self.run_capture(camera_capture=recorder)
        result = pixel_audit.audit_pixels(self.folder / 'out', case_id=CASE, diagnostic=True)
        self.assertEqual(result['decoded_original_pixels'], 3600)
        self.assertTrue(recorder.closed)

    def test_camera_recorder_rejects_wrong_frame_before_archiving(self):
        wrong = types.SimpleNamespace(frame=7, width=2, height=2,
                                      raw_data=bytes([3, 2, 1, 255] * 4))
        recorder = camera_recorder.CameraRecorder(
            self.folder / 'out', lambda frame: {key: wrong for key in camera_recorder.CAMERAS},
            case_id=CASE,
            source_ids={key: 'synthetic-' + key for key in camera_recorder.CAMERAS},
            sizes={key: (2, 2) for key in camera_recorder.CAMERAS})
        with self.assertRaisesRegex(ValueError, 'frame or dimensions mismatch'):
            self.run_capture(camera_capture=recorder)
        self.assertTrue(recorder.closed)
        self.assertFalse((self.folder / 'out' / 'front.zip').exists())


if __name__ == '__main__': unittest.main()
