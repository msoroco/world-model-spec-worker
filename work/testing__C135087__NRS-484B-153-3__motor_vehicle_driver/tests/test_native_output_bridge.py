"""Small synthetic Core projection test; no physical acceptance claim."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_output_bridge as bridge


class NativeOutputBridgeTests(unittest.TestCase):
    def test_source_joined_projection_and_seal(self):
        scratch = REPO / '.runtime-work/c135087-owner-nov26/temp'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            root = Path(temp)
            map_bytes = b'<OpenDRIVE/>'
            frames = [{'frame': 100 + i, 'time_s': i / 20} for i in range(3)]
            body = [[-1, 1], [1, 1], [1, 3], [-1, 3]]
            packets = {
                'frame_map': {'frames': frames},
                'door': {'samples': [dict(row, open=i == 1, side='left', angle_deg=70 if i == 1 else 0)
                                     for i, row in enumerate(frames)]},
                'activity': {'samples': [dict(row, active=i == 1, kind='cargo',
                                             loading_actor_id='3', speed_mps=.2 if i == 1 else 0,
                                             body_xy_m=body) for i, row in enumerate(frames)]},
                'passing_vehicle': {'samples': [dict(row, vehicle_id='2', center_x_m=-2 + i,
                                                    center_y_m=2, body_xy_m=body,
                                                    width_m=1, length_m=2) for i, row in enumerate(frames)]},
                'geometry': {'selected_vehicle_id': '1', 'passing_vehicle_id': '2',
                             'map_sha256': hashlib.sha256(map_bytes).hexdigest(),
                             'selected_vehicle_center_x_m': 0, 'selected_vehicle_center_y_m': 0,
                             'selected_vehicle_width_m': 2, 'selected_vehicle_length_m': 4,
                             'selected_vehicle_blueprint': 'vehicle.test.selected',
                             'passing_vehicle_blueprint': 'vehicle.test.passing',
                             'loading_actor_blueprint': 'static.prop.test'}}
            refs = {}
            for name, packet in packets.items():
                path = root / (name + '.json')
                path.write_text(json.dumps(packet) + '\n')
                refs[name] = {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            (root / 'inventory.json').write_text(json.dumps({'sources': refs, 'frame_count': 3,
                                                               'survey_sha256': 'a' * 64}) + '\n')
            (root / 'config.json').write_text('{}\n')
            (root / 'construction.json').write_text('{}\n')
            (root / 'runner.py').write_text('# synthetic bridge test\n')
            image = Image.new('RGB', (4, 4), color=(20, 40, 60))
            stream = io.BytesIO()
            image.save(stream, format='PNG')
            for view in bridge.VIEWS:
                folder = root / 'cameras' / view
                folder.mkdir(parents=True)
                for row in frames:
                    (folder / f'{row["frame"]:06d}.png').write_bytes(stream.getvalue())
            with patch.object(bridge, 'FRAME_COUNT', 3):
                receipt = bridge.publish(root, map_bytes=map_bytes, restored=True)
            self.assertEqual(receipt['frames'], 3)
            self.assertEqual(receipt['events'], ['capture_finished', 'encoders_closed', 'restoration_verified'])
            self.assertEqual(len((root / 'capture/native/frames.jsonl').read_text().splitlines()), 3)
            self.assertTrue(all((root / (name + '.mkv')).is_file() for name in bridge.VIEWS))


if __name__ == '__main__':
    unittest.main()
