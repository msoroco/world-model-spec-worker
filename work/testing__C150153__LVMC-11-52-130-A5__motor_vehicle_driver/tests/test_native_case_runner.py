"""The Native case test uses a fake adapter and makes no physical claim."""
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from native_case_runner import run_case
from parking import CASES
from test_native_history_capture import Adapter as CaptureAdapter
from test_parking import Adapter as ConstructionAdapter
from test_reviewed_site import ReviewedSiteTests


class CombinedAdapter(ConstructionAdapter):
    def __init__(self, source_site, case, mutate=None):
        super().__init__()
        self.capture = CaptureAdapter(source_site, case, mutate=mutate)

    def tick_and_sample(self):
        return self.capture.tick_and_sample()

    def read_fixture(self, fixture):
        self.calls.append(('readback', fixture))
        site = self.capture.site
        return {'identity_sha256': site['fixture_identity_sha256'],
                'geometry_sha256': site['fixture_geometry_sha256'],
                'physically_present': True}


class NativeCaseRunnerTests(unittest.TestCase):
    def test_reviewed_source_to_original_capture_and_cleanup(self):
        scratch = Path('.runtime-work/c150153-native-runner-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temp:
            packet_path, sources, packet = ReviewedSiteTests().make_packet(temp)
            source_site = dict(packet['site'])
            source_site['site_sha256'] = hashlib.sha256(packet_path.read_bytes()).hexdigest()
            case = next(c for c in CASES if c.id == 'west_inside')
            adapter = CombinedAdapter(source_site, case)
            output = Path(temp) / 'original-history.jsonl'
            result = run_case(adapter, packet_path, sources, HERE.name + '__west_inside',
                              4.0, output)
            self.assertEqual(result['frame_count'], 900)
            self.assertEqual(result['site_packet_sha256'], source_site['site_sha256'])
            self.assertEqual([call for call in adapter.calls if call[0] == 'destroy'],
                             [('destroy', 'ego'), ('destroy', 'fixture')])
            self.assertEqual(len(output.read_text().splitlines()), 900)
            wrong = json.loads(packet_path.read_text())
            wrong['sources']['map']['sha256'] = 'bad'
            packet_path.write_text(json.dumps(wrong) + '\n')
            with self.assertRaisesRegex(ValueError, 'hash differs: map'):
                run_case(adapter, packet_path, sources, HERE.name + '__west_inside',
                         4.0, Path(temp) / 'other.jsonl')

    def test_capture_failure_releases_owned_actors(self):
        scratch = Path('.runtime-work/c150153-native-runner-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temp:
            packet_path, sources, packet = ReviewedSiteTests().make_packet(temp)
            source_site = dict(packet['site'])
            source_site['site_sha256'] = hashlib.sha256(packet_path.read_bytes()).hexdigest()
            case = next(c for c in CASES if c.id == 'east_inside')
            def bad_frame(index, row):
                if index == 400:
                    row['original_frame'] += 1
            adapter = CombinedAdapter(source_site, case, mutate=bad_frame)
            output = Path(temp) / 'failed-history.jsonl'
            with self.assertRaisesRegex(ValueError, 'original frame mismatch'):
                run_case(adapter, packet_path, sources, HERE.name + '__east_inside',
                         4.0, output)
            self.assertFalse(output.exists())
            self.assertFalse(output.with_name(output.name + '.incomplete').exists())
            self.assertEqual([call for call in adapter.calls if call[0] == 'destroy'],
                             [('destroy', 'ego'), ('destroy', 'fixture')])


if __name__ == '__main__':
    unittest.main()
