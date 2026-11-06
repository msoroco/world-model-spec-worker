import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from finalize import CAMERAS,CHANNELS,finalize
from test_measure_native import create,put,put_rows


def prepare(root):
    create(root)
    config=json.loads((root/'config.json').read_text())
    put(root/'capture/manifest.json',{'case_id':config['case_id'],
        'frames':3,'extraction_confirmed':True})
    mapping=[json.loads(s) for s in (root/'video_frames.jsonl').read_text().splitlines()]
    for row in mapping:row['original_rgb_sha256']={name:'a'*64 for name in CAMERAS}
    put_rows(root/'video_frames.jsonl',mapping)
    for name in CHANNELS:
        put_rows(root/'channels'/(name+'.jsonl'),[
            {'native_frame':row['native_frame'],'time_s':row['time_s'],'value':{}}
            for row in mapping])
    for name in CAMERAS:(root/(name+'.mkv')).write_bytes(b'synthetic-test-video-placeholder')


class FinalizerTest(unittest.TestCase):
    def test_saved_result_preserves_visibility_uncertainty(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);prepare(root)
            with patch('finalize.video_frames',return_value=3):
                report=finalize(root,root/'analysis-report.json')
            result=json.loads((root/'result.json').read_text())
            self.assertEqual(report['format'],'c104538-saved-analysis-v1')
            self.assertFalse(result['setup_confirmed'])
            self.assertFalse(result['target_checks'][0]['matched'])
            self.assertFalse(result['accepted'])
            self.assertFalse(result['legal_verdict_claimed'])
            self.assertEqual(len(result['recording_evidence']),8)

    def test_incomplete_capture_and_channel_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);prepare(root)
            put(root/'capture/manifest.json',{'case_id':json.loads((root/'config.json').read_text())['case_id'],
                'frames':3,'extraction_confirmed':False})
            with self.assertRaisesRegex(ValueError,'capture extraction incomplete'):
                finalize(root,root/'analysis-report.json')
            put(root/'capture/manifest.json',{'case_id':json.loads((root/'config.json').read_text())['case_id'],
                'frames':3,'extraction_confirmed':True})
            (root/'channels'/'st.sight_distance.jsonl').unlink()
            with patch('finalize.video_frames',return_value=3):
                with self.assertRaisesRegex(ValueError,'Missing required source'):
                    finalize(root,root/'analysis-report.json')


if __name__=='__main__':unittest.main()
