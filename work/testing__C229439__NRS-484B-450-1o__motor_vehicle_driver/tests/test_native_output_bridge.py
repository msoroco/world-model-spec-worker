import io
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile
from types import SimpleNamespace as NS

from PIL import Image

FOLDER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FOLDER))
LOCAL_PIPELINE = FOLDER.parents[1] / 'runtime/scenario_pipeline'
if LOCAL_PIPELINE.is_dir():
    sys.path.insert(0, str(LOCAL_PIPELINE))
from native_output_bridge import encode_archive, seal, write_jsonl


class NativeBridgeTests(unittest.TestCase):
    def test_900_frame_original_source_projection_and_closure(self):
        scratch = Path(os.environ['TMPDIR'])
        with tempfile.TemporaryDirectory(dir=scratch, prefix='c229439-bridge-full-') as temporary:
            root = Path(temporary)
            def save(name, value):
                path = root / name
                path.write_text(json.dumps(value, separators=(',', ':')) + '\n')
                return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            map_text = '<OpenDRIVE/>'
            polygon = [[-2, -2], [2, -2], [2, 2], [-2, 2]]
            case = {'case_id': 'synthetic-bridge-test', 'halt_action': 'park'}
            save('config.json', {'case': case})
            save('construction.json', {'case_id': case['case_id']})
            (root / 'runner.py').write_text('# synthetic bridge test\n')
            save('site-source.json', {'cell_id': 'C229439', 'parking_polygon': polygon,
                                      'native_opendrive_sha256': hashlib.sha256(map_text.encode()).hexdigest()})
            save('device-source.json', {'device_id': 'diagnostic-sign', 'exact_instruction': 'NO PARKING',
                'governed_polygon': polygon, 'authority_source': 'synthetic diagnostic',
                'placement_source': 'synthetic diagnostic', 'traffic_purpose_source': 'synthetic diagnostic',
                'legal_consistency_source': 'synthetic diagnostic'})
            save('vehicle-source.json', {'blueprint': 'vehicle.tesla.model3'})
            save('context-source.json', {'diagnostic_fixture': True})
            image = io.BytesIO()
            Image.new('RGB', (4, 4), 'red').save(image, format='PNG')
            png = image.getvalue()
            pixel_sha = hashlib.sha256(png).hexdigest()
            cameras = {}
            for name in ('front', 'rear', 'left', 'right'):
                path = root / (name + '.png.zip')
                with ZipFile(path, 'w', compression=ZIP_STORED) as archive:
                    for frame in range(1, 901):
                        archive.writestr(f'{frame:08d}.png', png)
                cameras[name] = {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                 'frame_count': 900, 'fps': 20, 'dimensions': [4, 4]}
            rows = []
            for index in range(900):
                frame = index + 1
                rows.append({'frame': frame, 'time_s': round(index / 20, 2), 'case_id': case['case_id'],
                    'subject_id': '7', 'device_id': 'diagnostic-sign', 'device_instruction': 'NO PARKING',
                    'device_effective': True, 'prohibited_actions': ['park'],
                    'halt_activity': 'park' if index >= 400 else 'travel',
                    'traffic_conflict': False, 'police_direction': False, 'law_direction': False,
                    'device_direction': False, 'speed_mps': 0 if index >= 400 else 1,
                    'body_corners_xy': [[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]],
                    'body_vertices_m': [[x, y, z] for x in (-0.5, 0.5)
                                        for y in (-0.5, 0.5) for z in (0, 1)],
                    'position_m': [0, 0, 0], 'heading_deg': 0, 'velocity_mps': [0, 0, 0],
                    'camera_frames': {name: {'member': f'{frame:08d}.png', 'sha256': pixel_sha}
                                      for name in cameras}})
            row_ref = save('actor_rows.json', rows)
            map_ref = save('frame_map.json', [{'frame': row['frame'], 'time_s': row['time_s']} for row in rows])
            attempt = {'source_format': 'native_original', 'fps': 20, 'frame_count': 900, 'first_frame': 1,
                'case_id': case['case_id'], 'subject_id': '7', 'device_id': 'diagnostic-sign',
                'device_instruction': 'NO PARKING', 'parking_polygon': polygon, 'halt_action': 'park',
                'actor_rows': row_ref, 'frame_map': map_ref, 'cameras': cameras, 'camera_archives': cameras}
            save('attempt.json', attempt)
            world = NS(get_map=lambda: NS(to_opendrive=lambda: map_text))
            with self.assertRaisesRegex(ValueError, 'restoration required'):
                seal(root, world, restoration_verified=False, expected_dimensions={name: [4, 4] for name in cameras})
            sealed = seal(root, world, restoration_verified=True,
                          expected_dimensions={name: [4, 4] for name in cameras})
            receipt = json.loads(sealed.read_text())
            self.assertEqual(receipt['events'], ['capture_finished', 'encoders_closed', 'restoration_verified'])
            self.assertEqual(len((root / 'capture/native/frames.jsonl').read_text().splitlines()), 900)
            self.assertEqual(set(receipt['encoder_exit_codes']),
                             {'overview', 'approach', 'reference_corner', 'driver_reference'})
            self.assertTrue(all(name + '.mkv' in receipt['sources'] for name in receipt['encoder_exit_codes']))
            from worker_exchange.saved_processing import record_native_exit
            exit_receipt = record_native_exit(root)
            self.assertEqual(exit_receipt['capture_seal_sha256'], hashlib.sha256(sealed.read_bytes()).hexdigest())

    def test_original_png_archive_encodes_in_frame_order(self):
        scratch = Path(os.environ['TMPDIR'])
        with tempfile.TemporaryDirectory(dir=scratch, prefix='c229439-bridge-') as temporary:
            root = Path(temporary)
            archive = root / 'front.png.zip'
            members = ['00000001.png', '00000002.png']
            with ZipFile(archive, 'w', compression=ZIP_STORED) as output:
                for name, color in zip(members, ('red', 'blue')):
                    image = io.BytesIO()
                    Image.new('RGB', (4, 4), color).save(image, format='PNG')
                    output.writestr(name, image.getvalue())
            receipt = encode_archive(archive, root / 'overview.mkv', members)
            self.assertEqual(receipt['frames'], 2)
            self.assertTrue((root / 'overview.mkv').is_file())
            with self.assertRaisesRegex(ValueError, 'member order differs'):
                encode_archive(archive, root / 'other.mkv', list(reversed(members)))

    def test_jsonl_refuses_original_overwrite(self):
        scratch = Path(os.environ['TMPDIR'])
        with tempfile.TemporaryDirectory(dir=scratch, prefix='c229439-bridge-') as temporary:
            path = Path(temporary) / 'trace.jsonl'
            write_jsonl(path, [{'frame': 1}])
            with self.assertRaisesRegex(ValueError, 'already exists'):
                write_jsonl(path, [{'frame': 2}])


if __name__ == '__main__':
    unittest.main()
