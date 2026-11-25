import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import analysis
from encounter import CASES
from native_acquisition import capture
from test_native_acquisition import Adapter, actors
from test_carla_adapter import cameras
from build_semantic_draft import description


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n', encoding='utf-8')


def fixture(root):
    case = CASES[0]
    access = root / 'access-source.txt'
    access.write_text('Diagnostic public-access document.\n', encoding='utf-8')
    review = root / 'access-review.json'
    write(review, {'source_kind': 'synthetic_fixture',
                   'public_access_basis': 'highway', 'source_sha256': sha(access)})
    camera = root / 'camera-plan.json'
    plan = cameras()
    write(camera, plan)
    site_path = root / 'site.json'
    write(site_path, {'site_id': 'diagnostic-intersection',
                      'public_access_basis': 'highway',
                      'public_access_review_sha256': sha(review)})
    canonical = json.dumps(plan, sort_keys=True, separators=(',', ':')).encode()
    source = {'site_sha256': sha(site_path), 'map_sha256': 'b' * 64,
              'camera_plan_sha256': hashlib.sha256(canonical).hexdigest(),
              'public_access_basis': 'highway'}
    capture(Adapter(case=case), actors(case), case, source, root)


class AnalysisTests(unittest.TestCase):
    def test_source_derived_trace_and_recording_result(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            receipt = json.loads((root / 'native-receipt.json').read_text())
            write(root / 'construction.json', {
                'case_id': receipt['case_id'],
                'recording_description': description(),
            })
            write(root / 'config.json', {'selected_case_id': receipt['case_id']})
            for name in ('front', 'rear', 'left', 'right'):
                (root / (name + '.mkv')).write_bytes(b'diagnostic-video-placeholder')
            report = analysis.analyze(root, allow_diagnostic=True)
            result = analysis.finalize_native_outputs(root, report)
            self.assertEqual(len((root / 'trace.jsonl').read_text().splitlines()), 900)
            self.assertEqual(len((root / 'video_frames.jsonl').read_text().splitlines()), 900)
            self.assertEqual(len(result['video_references']), 4)
            self.assertEqual(result['recording_description'], description())
            self.assertEqual(len(result['recording_evidence']), 7)
            with self.assertRaisesRegex(ValueError, 'derived output already exists'):
                analysis.finalize_native_outputs(root, report)

    def test_source_shaped_diagnostic_measurements_and_missing_source(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            with self.assertRaisesRegex(ValueError, 'original public-access source join failed'):
                analysis.analyze(root)
            report = analysis.analyze(root, allow_diagnostic=True)
            self.assertEqual(set(report['measurements']),
                             {'access_context', 'driver_control_history',
                              'person_encounter', 'property_encounter'})
            self.assertEqual(report['measurements']['access_context']['value']['source_kind'],
                             'synthetic_fixture')
            self.assertIsNone(report['legal_judgment'])
            (root / 'access-source.txt').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source: access-source.txt'):
                analysis.analyze(root, allow_diagnostic=True)


if __name__ == '__main__':
    unittest.main()
