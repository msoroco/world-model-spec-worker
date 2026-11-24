"""CPU binding checks for the original Native to saved-only boundary."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from test_construction import survey

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_seal', ROOT / 'native_seal.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
CASE = ROOT.name + '__near_centerline'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SealTests(unittest.TestCase):
    def _sources(self, root):
        source = root / 'road.xodr'
        source.write_text('<OpenDRIVE/>\n')
        packet = survey()
        packet['source_sha256'] = sha(source)
        packet['map_source_path'] = source.name
        for road in packet['intersecting_roads']:
            road['highway_review_status'] = 'source_verified'
            review_path = root / f'review-road-{road["road_id"]}.json'
            review_path.write_text(json.dumps({
                'road_id': road['road_id'], 'highway_status': 'source_verified',
                'alley': False, 'reviewer': 'diagnostic-fixture-reviewer',
                'source_citation': 'diagnostic only; no real highway determination',
            }) + '\n')
            road['public_highway_source'] = {'path': review_path.name,
                                             'sha256': sha(review_path)}
        survey_path = root / 'survey.json'
        survey_path.write_text(json.dumps(packet) + '\n')
        attempt = root / 'attempt'
        attempt.mkdir()
        trace = attempt / 'original-trace.json'
        trace.write_text('{"case_id":"' + CASE + '"}\n')
        camera = attempt / 'original-camera-index.json'
        camera.write_text('{"case_id":"' + CASE + '"}\n')
        receipt = {'case_id': CASE, 'frames': 900, 'trace_path': str(trace),
                   'trace_sha256': sha(trace), 'camera_index_path': str(camera),
                   'camera_index_sha256': sha(camera)}
        return source, survey_path, attempt, receipt

    def test_sealed_manifest_binds_original_map_trace_and_camera(self):
        with tempfile.TemporaryDirectory() as directory:
            source, survey_path, attempt, receipt = self._sources(Path(directory))
            result = module.seal(attempt, case_id=CASE, survey_path=survey_path,
                                 survey_sha256=sha(survey_path), map_source_path=source,
                                 capture_receipt=receipt)
            manifest = json.loads(Path(result['source_manifest_path']).read_text())
            self.assertEqual(manifest['acquisition_kind'], 'original_native')
            self.assertEqual(manifest['map']['sha256'], sha(attempt / 'original-map-packet.json'))
            self.assertEqual(manifest['trace']['sha256'], sha(attempt / 'original-trace.json'))
            self.assertFalse(manifest['physical_completion'])
            self.assertIsNone(manifest['statutory_judgment'])
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                module.seal(attempt, case_id=CASE, survey_path=survey_path,
                            survey_sha256=sha(survey_path), map_source_path=source,
                            capture_receipt=receipt)

    def test_highway_review_and_changed_original_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source, survey_path, attempt, receipt = self._sources(Path(directory))
            packet = json.loads(survey_path.read_text())
            packet['intersecting_roads'][0].pop('highway_review_status')
            survey_path.write_text(json.dumps(packet) + '\n')
            with self.assertRaisesRegex(ValueError, 'highway review'):
                module.seal(attempt, case_id=CASE, survey_path=survey_path,
                            survey_sha256=sha(survey_path), map_source_path=source,
                            capture_receipt=receipt)
            packet['intersecting_roads'][0]['highway_review_status'] = 'source_verified'
            survey_path.write_text(json.dumps(packet) + '\n')
            source.write_text('<OpenDRIVE changed="1"/>\n')
            with self.assertRaisesRegex(ValueError, 'OpenDRIVE map source differs'):
                module.seal(attempt, case_id=CASE, survey_path=survey_path,
                            survey_sha256=sha(survey_path), map_source_path=source,
                            capture_receipt=receipt)

    def test_rehashed_review_must_have_source_conclusion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, survey_path, attempt, receipt = self._sources(root)
            packet = json.loads(survey_path.read_text())
            binding = packet['intersecting_roads'][0]['public_highway_source']
            review_path = root / binding['path']
            review = json.loads(review_path.read_text())
            review.pop('source_citation')
            review_path.write_text(json.dumps(review) + '\n')
            binding['sha256'] = sha(review_path)
            survey_path.write_text(json.dumps(packet) + '\n')
            with self.assertRaisesRegex(ValueError, 'review conclusion missing'):
                module.seal(attempt, case_id=CASE, survey_path=survey_path,
                            survey_sha256=sha(survey_path), map_source_path=source,
                            capture_receipt=receipt)


if __name__ == '__main__':
    unittest.main()
