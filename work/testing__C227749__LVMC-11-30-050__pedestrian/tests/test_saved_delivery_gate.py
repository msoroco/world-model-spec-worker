import importlib.util
import json
import pathlib
import tempfile
import unittest


BASE = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('saved_delivery_gate', BASE / 'saved_delivery_gate.py')
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


class SavedDeliveryGateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = pathlib.Path(self.temp.name)
        self.attempt = root / 'attempt'
        self.version = root / 'v0001'
        write(self.attempt / 'construction.json', {'case_id': 'case'})
        write(self.attempt / 'source.json', {'frame': 1})
        write(self.version / 'analysis' / 'result.json',
              {'case_id': 'case', 'provenance_kind': 'synthetic_fixture',
               'diagnostic_fixture': True})
        construction = GATE.sha(self.attempt / 'construction.json')
        self.receipt = {
            'format': 'worker-saved-processing', 'case_id': 'case',
            'recorded_only': True, 'passed': True, 'candidate_id': 'primary',
            'missing_evidence': False, 'originals_preserved': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
            'native_revision': {'construction_sha256': construction},
            'analysis_revision': {'construction_sha256': construction},
            'result_sha256': GATE.sha(self.version / 'analysis' / 'result.json'),
            'original_source_hashes': {'source.json': GATE.sha(self.attempt / 'source.json')},
            'timestamp_joins': {'passed': True, 'missing_original_trace_or_map': False, 'frames': 5},
            'final_video_checks': {'passed': True, 'frames': 5}}
        self.construction = construction
        self.save()

    def save(self):
        write(self.version / 'processing.json', self.receipt)

    def check(self):
        return GATE.audit(self.version, self.attempt, 'case', self.construction)

    def test_diagnostic_is_software_only(self):
        result = self.check()
        self.assertEqual(result['status'], 'software_diagnostic_complete')
        self.assertFalse(result['physical_acceptance'])
        self.assertEqual(result['legal_verdict'], 'unresolved')

    def test_changed_original_rejected(self):
        write(self.attempt / 'source.json', {'frame': 2})
        with self.assertRaisesRegex(ValueError, 'original source'):
            self.check()

    def test_missing_evidence_rejected(self):
        self.receipt['missing_evidence'] = True
        self.save()
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            self.check()

    def test_unsupported_acceptance_rejected(self):
        self.receipt['physical_acceptance_claimed'] = True
        self.save()
        with self.assertRaisesRegex(ValueError, 'unsupported acceptance'):
            self.check()

    def test_frame_mismatch_rejected(self):
        self.receipt['final_video_checks']['frames'] = 4
        self.save()
        with self.assertRaisesRegex(ValueError, 'frame join'):
            self.check()

    def test_stale_result_rejected(self):
        write(self.version / 'analysis' / 'result.json', {'case_id': 'case'})
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.check()

    def test_native_requires_map_readback(self):
        result_path = self.version / 'analysis' / 'result.json'
        write(result_path, {'case_id': 'case', 'provenance_kind': 'native'})
        self.receipt['result_sha256'] = GATE.sha(result_path)
        self.receipt['timestamp_joins']['frames'] = 400
        self.receipt['final_video_checks']['frames'] = 400
        self.save()
        with self.assertRaisesRegex(ValueError, 'map readback missing'):
            self.check()

    def test_native_map_identity_supports_source_review_only(self):
        result_path = self.version / 'analysis' / 'result.json'
        write(result_path, {'case_id': 'case', 'provenance_kind': 'native'})
        self.receipt['result_sha256'] = GATE.sha(result_path)
        self.receipt['timestamp_joins']['frames'] = 400
        self.receipt['final_video_checks']['frames'] = 400
        self.attempt.mkdir(parents=True, exist_ok=True)
        (self.attempt / 'candidate-crossing.xodr').write_text('<OpenDRIVE/>\n')
        map_sha = GATE.sha(self.attempt / 'candidate-crossing.xodr')
        write(self.attempt / 'scene.json', {'map_source_sha256': map_sha,
                                          'crosswalk_boundaries_xy_m': [[[0, 0], [1, 0], [1, 1], [0, 1]]]})
        packet = self.attempt / 'native-crosswalk-readback.json'
        write(packet, {'case_id': 'case', 'loaded_map_sha256': map_sha,
                       'native_crosswalk_vertices': 4,
                       'authored_polygon_readbacks': [{'vertices': 4,
                                                       'maximum_vertex_readback_gap_m': 0.2}]})
        self.receipt['original_source_hashes']['native-crosswalk-readback.json'] = GATE.sha(packet)
        self.save()
        checked = self.check()
        self.assertEqual(checked['status'], 'native_sources_ready_for_physical_review')
        self.assertFalse(checked['physical_acceptance'])
        write(packet, {'case_id': 'case', 'loaded_map_sha256': '0' * 64})
        self.receipt['original_source_hashes']['native-crosswalk-readback.json'] = GATE.sha(packet)
        self.save()
        with self.assertRaisesRegex(ValueError, 'source/case mismatch'):
            self.check()


if __name__ == '__main__':
    unittest.main()
