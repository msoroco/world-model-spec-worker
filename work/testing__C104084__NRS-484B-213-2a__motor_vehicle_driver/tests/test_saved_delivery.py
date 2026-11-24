import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from saved_delivery import process
from test_saved_crest import fixture

ASSIGNMENT = ROOT.name
CASE = ASSIGNMENT + '__left_crest_obstructed'
CAMERAS = ('forward', 'left', 'right', 'rear')


def video_attempt(attempt):
    hashes = fixture(attempt)
    for camera in CAMERAS:
        path = attempt / f'camera-{camera}.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        'color=c=blue:s=32x24:r=20', '-frames:v', '3',
                        '-c:v', 'mpeg4', '-y', str(path)], check=True)
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (attempt / 'source-hashes.json').write_text(json.dumps(hashes) + '\n',
                                                encoding='utf-8')
    return hashes


class SavedDeliveryTests(unittest.TestCase):
    def test_joins_original_observations_and_all_decoded_cameras(self):
        with tempfile.TemporaryDirectory() as temporary:
            attempt = Path(temporary) / 'original'
            attempt.mkdir()
            hashes = video_attempt(attempt)
            output = Path(temporary) / 'saved' / 'receipt.json'
            result = process(attempt, output, assignment_id=ASSIGNMENT,
                             case_id=CASE, expected_frames=3,
                             expected_dimensions={camera: (32, 24) for camera in CAMERAS})
            self.assertEqual(result, json.loads(output.read_text()))
            self.assertEqual(result['observation']['source_sha256']['camera-left.mp4'],
                             hashes['camera-left.mp4'])
            self.assertEqual(result['media']['cameras']['left']['sha256'],
                             hashes['camera-left.mp4'])
            self.assertFalse(result['physical_visibility_reviewed'])
            with self.assertRaisesRegex(ValueError, 'retain prior'):
                process(attempt, output, assignment_id=ASSIGNMENT,
                        case_id=CASE, expected_frames=3)

    def test_bad_media_or_source_manifest_leaves_no_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            attempt = Path(temporary) / 'original'
            attempt.mkdir()
            hashes = video_attempt(attempt)
            output = Path(temporary) / 'saved.json'
            camera = attempt / 'camera-left.mp4'
            camera.write_bytes(b'broken original video')
            hashes[camera.name] = hashlib.sha256(camera.read_bytes()).hexdigest()
            (attempt / 'source-hashes.json').write_text(json.dumps(hashes) + '\n')
            with self.assertRaisesRegex(ValueError, 'media decode failed'):
                process(attempt, output, assignment_id=ASSIGNMENT,
                        case_id=CASE, expected_frames=3)
            self.assertFalse(output.exists())
            hashes['unplanned.txt'] = '0' * 64
            (attempt / 'source-hashes.json').write_text(json.dumps(hashes) + '\n')
            with self.assertRaisesRegex(ValueError, 'wrong exact sources'):
                process(attempt, output, assignment_id=ASSIGNMENT,
                        case_id=CASE, expected_frames=3)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
