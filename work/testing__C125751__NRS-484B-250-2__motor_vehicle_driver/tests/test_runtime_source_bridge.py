import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from entry_timing import ASSIGNMENT
from native_capture import capture
from runtime_source_bridge import export
from test_entry_timing import survey
from test_native_capture import Adapter


class RuntimeSourceBridgeTests(unittest.TestCase):
    def test_sealed_sources_become_four_named_videos_and_native_trace(self):
        scratch = Path(__file__).resolve().parents[3]/'.runtime-work'/'c125751-bridge-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            packet = survey()
            packet['opendrive_sha256'] = hashlib.sha256(b'original map').hexdigest()
            packet['runtime_camera_roles'] = {'overview': 'front', 'approach': 'rear',
                                              'reference_corner': 'left', 'driver_reference': 'right'}
            source = root/'survey.json'
            source.write_text(json.dumps(packet)+'\n')
            map_path = root/'original.xodr'
            map_path.write_bytes(b'original map')
            attempt = root/'attempt'
            capture(Adapter(), source, hashlib.sha256(source.read_bytes()).hexdigest(),
                    map_path, ASSIGNMENT+'__precedence', attempt)
            profile = {'fps': 20, 'overview': [4, 4],
                       'detail_views': [[4, 4], [4, 4], [4, 4]]}
            receipt = export(attempt, source, root/'derived', profile)
            self.assertEqual(set(receipt['videos']), {'overview', 'approach',
                             'reference_corner', 'driver_reference'})
            self.assertTrue(all(item['decoded_frames'] == 900
                                for item in receipt['videos'].values()))
            rows = [json.loads(line) for line in (root/'derived/trace.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows), 900)
            self.assertEqual(rows[0]['frame'], 1000)
            self.assertEqual(rows[-1]['frame'], 1899)
            self.assertEqual(rows[0]['time_s'], 50)
            self.assertFalse(receipt['physical_acceptance_claimed'])
            with self.assertRaisesRegex(ValueError, 'fresh destination'):
                export(attempt, source, root/'derived', profile)

    def test_role_mapping_is_required_before_encoding(self):
        scratch = Path(__file__).resolve().parents[3]/'.runtime-work'/'c125751-bridge-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            packet = survey()
            packet['opendrive_sha256'] = hashlib.sha256(b'original map').hexdigest()
            source = root/'survey.json'
            source.write_text(json.dumps(packet)+'\n')
            map_path = root/'original.xodr'
            map_path.write_bytes(b'original map')
            attempt = root/'attempt'
            capture(Adapter(), source, hashlib.sha256(source.read_bytes()).hexdigest(),
                    map_path, ASSIGNMENT+'__precedence', attempt)
            with self.assertRaisesRegex(ValueError, 'role mapping'):
                export(attempt, source, root/'derived')
            self.assertFalse((root/'derived').exists())


if __name__ == '__main__':
    unittest.main()
