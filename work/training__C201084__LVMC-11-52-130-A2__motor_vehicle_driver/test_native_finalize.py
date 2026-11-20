"""Saved-only finalizer tests on explicitly synthetic source packets."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from fire_lane_survey import CAMERAS
from native_finalize import finalize
from test_source_measurement import make_attempt


HERE = Path(__file__).resolve().parent


def fixture(path):
    make_attempt(path, 'reference')
    construction = json.loads((HERE/'draft-reference-construction.json').read_text())
    config = json.loads(next(row['content'] for row in construction['files']
                             if row['path'] == 'config.json'))
    (path/'config.json').write_text(json.dumps(config)+'\n')
    (path/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True})+'\n')
    for name in CAMERAS:
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                        '-f', 'lavfi', '-i', 'color=c=black:s=16x16:r=20',
                        '-frames:v', '4', '-c:v', 'ffv1',
                        str(path/(name+'.mkv'))], check=True)


class FinalizeTests(unittest.TestCase):
    def test_saved_source_derivation_preserves_originals_and_withholds_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            fixture(path)
            before = {name: (path/name).read_bytes() for name in
                      ('native-actors.jsonl','video_frames.jsonl',
                       'native-survey-readback.json')}
            report = finalize(path, path/'analysis-report.json')
            self.assertEqual(report['provenance_kind'], 'synthetic_fixture')
            self.assertTrue(report['diagnostic_fixture'])
            self.assertFalse(report['physical_acceptance_claimed'])
            self.assertFalse(report['legal_verdict_claimed'])
            self.assertEqual(report['measurements']['authored_zone_stop']['value']
                             ['near_zero_with_overlap_frames'], 2)
            result = json.loads((path/'result.json').read_text())
            self.assertFalse(result['setup_confirmed'])
            self.assertFalse(result['maneuver_completed'])
            self.assertEqual(len((path/'trace.jsonl').read_text().splitlines()), 4)
            channel = [json.loads(line) for line in
                       (path/'channels/vehicle_stops_in_posted_fire_lane.jsonl')
                       .read_text().splitlines()]
            self.assertTrue(all(row['value'] is None for row in channel))
            self.assertEqual(before, {name: (path/name).read_bytes()
                                      for name in before})
            with self.assertRaisesRegex(ValueError, 'Retain previous Native result'):
                finalize(path, path/'second-report.json')

    def test_missing_camera_rejected_before_derived_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            fixture(path)
            (path/'reference_corner.mkv').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing original source camera'):
                finalize(path, path/'analysis-report.json')
            self.assertFalse((path/'channels').exists())
            self.assertFalse((path/'result.json').exists())

    def test_native_marker_cannot_relabel_synthetic_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            fixture(path)
            (path/'acquisition-provenance.json').write_text(json.dumps({
                'provenance_kind': 'native', 'diagnostic_fixture': False})+'\n')
            with self.assertRaises(ValueError):
                finalize(path, path/'analysis-report.json')
            self.assertFalse((path/'result.json').exists())


if __name__ == '__main__':
    unittest.main()
