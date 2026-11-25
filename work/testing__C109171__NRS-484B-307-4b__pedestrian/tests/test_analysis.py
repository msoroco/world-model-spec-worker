import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import analysis
from build_offline_draft import RECORDING_DESCRIPTION


class AnalysisTest(unittest.TestCase):
    def test_source_bound_report_and_native_result(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd() / '.runtime-work') as directory:
            root = Path(directory)
            (root / 'construction.json').write_text(json.dumps({
                'recording_description': RECORDING_DESCRIPTION}))
            source = {'case_id': 'exact-case', 'frame_map_ref': {'path': 'original_frame_map.json'}}
            measured = {'sole_green_arrow_frames': 2, 'first_highway_entry': None,
                        'separate_walk_first_frame': None, 'separate_walk_frame_count': 0,
                        'original_site_sha256': 'site-sha'}
            rows = [{'frame': n, 'sim_time_seconds': n * 0.05,
                     'pedestrian_xy': [-2, 1], 'pedestrian_device_id': 'ped-1',
                     'pedestrian_device_indication': 'DONT_WALK',
                     'vehicle_head_id': 'head-1',
                     'vehicle_head_lit_aspects': ['green-left-arrow']} for n in range(2)]
            with patch('analysis._input', return_value=(source, measured, rows,
                  {'pedestrian-source.json': 'a', 'site.json': 'b', 'original_events.json': 'c'})):
                report = analysis.analyze(root, root / 'analysis-report.json')
            self.assertEqual(report['measurements']['sole_arrow_and_facing']['value']['sole_green_arrow_frames'], 2)
            result = json.loads((root / 'result.json').read_text())
            self.assertEqual(result['case_id'], 'exact-case')
            self.assertFalse(result['setup_confirmed'])
            self.assertEqual(len(result['recording_evidence']), 5)
            self.assertTrue((root / 'channels/separate_device_timeline.jsonl').is_file())

    def test_missing_case_source_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd() / '.runtime-work') as directory:
            with self.assertRaisesRegex(ValueError, 'Missing required source: pedestrian-source.json'):
                analysis.analyze(Path(directory), Path(directory) / 'analysis-report.json')


if __name__ == '__main__':
    unittest.main()
