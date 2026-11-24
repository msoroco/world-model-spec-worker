import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from test_native_capture import World, CAMERAS, control, media_factory, transform
from native_capture import capture
from original_graph import collect
from core_projection import project


class CoreProjectionTests(unittest.TestCase):
    def test_original_graphs_and_motion_publish_source_bound_core_packet(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            world = World()
            case_id = ROOT.name + '__above'
            packet = {'format': 'c10301-native-site-v1', 'case_id': case_id,
                      'cell_id': 'C10301', 'layout': 'alley',
                      'control': 'access_aisle', 'actor': 'motor_vehicle_driver',
                      'maneuver': 'travel', 'diagnostic_fixture': True,
                      'map_name': world.map.name,
                      'opendrive_sha256': hashlib.sha256(
                          world.map.to_opendrive().encode()).hexdigest(),
                      'access_aisle_source_ref': 'diagnostic aisle',
                      'route_source_ref': 'diagnostic route',
                      'route': [{'s_m': 10 * i, 'x_m': 10 * i,
                                 'y_m': 0, 'z_m': 0} for i in range(181)],
                      'vehicle_blueprint_id': 'vehicle.diagnostic',
                      'cameras': {name: {'blueprint_id': 'sensor.camera.rgb',
                                         'x_m': 0, 'y_m': 0, 'z_m': 1.5,
                                         'pitch_deg': 0, 'yaw_deg': 0,
                                         'roll_deg': 0} for name in CAMERAS}}
            site = folder / 'site.json'
            site.write_text(json.dumps(packet) + '\n')
            def graph_reader(world, actor, snapshot, frame, time_s):
                return collect(world, actor, snapshot, expected_frame=frame,
                               expected_time_s=snapshot.timestamp.elapsed_seconds,
                               recording_time_s=time_s)
            attempt = folder / 'attempt'
            capture(world, site, attempt, case_id, 'core-fixture', 0.05,
                    transform, control, diagnostic_fixture=True,
                    media_factory=media_factory, graph_reader=graph_reader)
            (attempt / 'recorder_info.txt').write_text(
                'Synthetic CPU fixture\nCreate 17: vehicle.diagnostic\n')
            output = folder / 'core'
            with self.assertRaisesRegex(ValueError, 'diagnostic fixture'):
                project(attempt, output, case_id)
            receipt = project(attempt, output, case_id,
                              allow_diagnostic=True)
            self.assertEqual(receipt['frames'], 900)
            self.assertTrue(receipt['diagnostic_fixture'])
            self.assertEqual(len((output / 'capture/evidence.jsonl').read_text().splitlines()), 900)
            self.assertEqual(len(list((output / 'capture/native/graphs/abstract').glob('*.adapter.json'))), 900)
            with self.assertRaisesRegex(ValueError, 'new separate Core source'):
                project(attempt, output, case_id, allow_diagnostic=True)
            source = attempt / 'graphs/abstract/00000140.adapter.json'
            source.write_bytes(source.read_bytes() + b'changed')
            with self.assertRaisesRegex(ValueError, 'Native graph source hash differs'):
                project(attempt, folder / 'changed', case_id,
                        allow_diagnostic=True)


if __name__ == '__main__':
    unittest.main()
