import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis import build, measure_yield_source
from native_capture import capture
from test_native_capture import FakeAdapter, fixture
from yield_view import CASES


class SelectedAnalysisTests(unittest.TestCase):
    def test_saved_source_contract_and_negative_file(self):
        scratch = Path.cwd() / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            case = CASES[0]
            packet = fixture(source, case)
            bundle = root / 'bundle'
            bundle.mkdir()
            original = bundle / 'original-attempt'
            capture(FakeAdapter(case), packet, source, original, case,
                    diagnostic=True)
            site_sha = hashlib.sha256(
                (original / 'reviewed-site-packet.json').read_bytes()).hexdigest()
            measured, hashes, audit = measure_yield_source(
                bundle, case, site_sha, allow_diagnostic=True)
            self.assertEqual(measured['case_id'], case.case_id)
            self.assertEqual(audit['decoded_camera_frames'], 3600)
            self.assertEqual(len(hashes), 4)
            with self.assertRaisesRegex(ValueError,
                                        'independent reviewed site hash differs'):
                measure_yield_source(bundle, case, '0' * 64,
                                     allow_diagnostic=True)
            construction = json.loads((ROOT / 'cases' / case.case_id /
                                       'construction.json').read_text())
            (bundle / 'construction.json').write_text(
                json.dumps(construction) + '\n')
            config = {
                'assignment_id': ROOT.name,
                'selected_case_id': ROOT.name + '__' + case.case_id,
                'approach_policy': case.approach_policy,
                'reviewed_site_packet_sha256': site_sha,
                'diagnostic_only': True,
            }
            (bundle / 'config.json').write_text(json.dumps(config) + '\n')
            rows = json.loads((original / 'rows.json').read_text())
            with (bundle / 'trace.jsonl').open('w') as trace, \
                    (bundle / 'video_frames.jsonl').open('w') as mapping:
                for i, row in enumerate(rows):
                    trace.write(json.dumps({'frame': row['original_frame'],
                                            'time_s': row['time_s']}) + '\n')
                    mapping.write(json.dumps({'video_frame': i,
                                              'carla_frame': row['original_frame'],
                                              'time_s': row['time_s']}) + '\n')
            for view in ('overview', 'approach', 'reference_corner',
                         'driver_reference'):
                (bundle / (view + '.mkv')).write_bytes(b'diagnostic placeholder')
            report, result = build(bundle)
            self.assertEqual(report['measurements']['nearest_view_yield_event']
                             ['value'], measured)
            self.assertFalse(result['physical_acceptance_claimed'])
            self.assertEqual(len(result['recording_evidence']), 10)
            self.assertEqual(len((bundle / 'channels/ego_speed.jsonl')
                                 .read_text().splitlines()), 900)
            (original / 'measurement.json').unlink()
            with self.assertRaisesRegex(
                    ValueError,
                    'Missing required source: original-attempt/measurement.json'):
                measure_yield_source(bundle, case, site_sha,
                                     allow_diagnostic=True)


if __name__ == '__main__':
    unittest.main()
