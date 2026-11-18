import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
spec = importlib.util.spec_from_file_location('c179480_saved_analysis', root / 'saved_analysis.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SavedAnalysisTest(unittest.TestCase):
    def sources(self, folder):
        rows = [dict(frame=101+i, ego_speed_mps=(2.0 if i == 0 else 0.0),
                     ego_on_roadway=True, ego_lane_overlap=True,
                     following_speed_mps=3.0-i,
                     following_gap_m=10.0-i) for i in range(3)]
        (folder / 'native-actors.jsonl').write_text(
            ''.join(json.dumps(row)+'\n' for row in rows))
        (folder / 'video_frames.jsonl').write_text(
            ''.join(json.dumps(dict(video_frame=i, carla_frame=101+i,
                                    time_s=i/20))+'\n' for i in range(3)))
        map_path = folder / 'native-map-readback.json'
        map_path.write_text(json.dumps(dict(format='c179480-original-map-readback-v1',
                                            map_name='test-road'))+'\n')
        measured = module.analyze(folder / 'native-actors.jsonl',
                                  folder / 'video_frames.jsonl')
        measured.update(format='c179480-source-measurements-v1', case='reference',
                        actor_source_sha256=module.sha256(folder / 'native-actors.jsonl'),
                        frame_map_sha256=module.sha256(folder / 'video_frames.jsonl'),
                        map_readback_sha256=module.sha256(map_path))
        (folder / 'source-measurements.json').write_text(json.dumps(measured)+'\n')
        video = folder / 'overview.mkv'
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                        '-f', 'lavfi', '-i', 'color=c=blue:s=16x16:r=20',
                        '-frames:v', '3', '-c:v', 'ffv1', str(video)], check=True)
        for camera in module.CAMERAS[1:]:
            (folder / (camera+'.mkv')).write_bytes(video.read_bytes())

    def test_all_original_sources_are_bound_and_missing_camera_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.sources(folder)
            output = folder / 'saved-review.json'
            result = module.review(folder, output)
            self.assertEqual(result['source_frames'], 3)
            self.assertEqual(set(result['source_sha256']),
                             {'native-actors.jsonl', 'video_frames.jsonl',
                              'native-map-readback.json', 'source-measurements.json',
                              *(name+'.mkv' for name in module.CAMERAS)})
            self.assertFalse(result['legal_verdict_claimed'])
            self.assertEqual(json.loads(output.read_text()), result)
            with self.assertRaisesRegex(ValueError, 'new output'):
                module.review(folder, output)
            (folder / 'approach.mkv').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing original source camera'):
                module.review(folder, folder / 'another-review.json')

    def test_stale_source_or_video_count_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.sources(folder)
            video = folder / 'driver_reference.mkv'
            subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                            '-f', 'lavfi', '-i', 'color=c=red:s=16x16:r=20',
                            '-frames:v', '2', '-c:v', 'ffv1', '-y', str(video)], check=True)
            with self.assertRaisesRegex(ValueError, 'camera count differs'):
                module.review(folder, folder / 'review.json')
            video.write_bytes((folder / 'overview.mkv').read_bytes())
            mapping = folder / 'video_frames.jsonl'
            lines = mapping.read_text().splitlines()
            mapping.write_text('\n'.join(lines[:-1])+'\n')
            with self.assertRaisesRegex(ValueError, 'length differs'):
                module.review(folder, folder / 'review.json')

    def test_tampered_map_readback_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.sources(folder)
            (folder / 'native-map-readback.json').write_text(
                json.dumps(dict(format='c179480-original-map-readback-v1',
                                map_name='changed-road'))+'\n')
            with self.assertRaisesRegex(ValueError, 'receipt differs'):
                module.review(folder, folder / 'review.json')

    def test_safe_operation_receipt_rejects_missing_original_hazard(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.sources(folder)
            map_file = folder/'native-map-readback.json'
            map_file.write_text(json.dumps(dict(
                format='c179480-original-map-readback-v1',
                map_name='test-road',case='safe_operation_stop'))+'\n')
            receipt_file = folder/'source-measurements.json'
            receipt = json.loads(receipt_file.read_text())
            receipt['case'] = 'safe_operation_stop'
            receipt['map_readback_sha256'] = module.sha256(map_file)
            receipt_file.write_text(json.dumps(receipt)+'\n')
            with self.assertRaisesRegex(ValueError,'Missing original safe-operation hazard'):
                module.review(folder,folder/'review.json')


if __name__ == '__main__':
    unittest.main()
