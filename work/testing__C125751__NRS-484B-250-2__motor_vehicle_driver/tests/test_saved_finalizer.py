import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from entry_timing import ASSIGNMENT
from native_capture import capture
from saved_finalizer import finalize
from delivery_audit import audit
from test_entry_timing import survey
from test_native_capture import Adapter


class SavedFinalizerTests(unittest.TestCase):
    def test_canonical_result_and_independent_saved_audit(self):
        scratch = Path(__file__).resolve().parents[3]/'.runtime-work'/'c125751-finalizer-tests'
        scratch.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            survey_packet = survey()
            survey_packet['opendrive_sha256'] = hashlib.sha256(b'original map').hexdigest()
            survey_path = root/'survey.json'
            survey_path.write_text(json.dumps(survey_packet)+'\n')
            map_path = root/'original.xodr'
            map_path.write_bytes(b'original map')
            attempt = root/'attempt'
            case = ASSIGNMENT+'__precedence'
            capture(Adapter(),survey_path,hashlib.sha256(survey_path.read_bytes()).hexdigest(),
                    map_path,case,attempt)
            video = attempt/'primary.mkv'
            subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','lavfi',
                            '-i','color=c=red:s=4x4:r=20:d=45','-frames:v','900',
                            '-c:v','ffv1',str(video)],check=True)
            result_path = finalize(attempt,survey_path,'primary.mkv')
            result = json.loads(result_path.read_text())
            self.assertEqual(result['case_id'],case)
            self.assertFalse(result['setup_confirmed'])
            self.assertFalse(result['target_checks'][0]['matched'])
            receipt = audit(attempt,survey_path)
            self.assertEqual(receipt['primary_video_decoded_frames'],900)
            self.assertFalse(receipt['physical_acceptance_claimed'])
            result['measured_values']['ego_minus_other_upper_entry_s'] = 99
            result_path.write_text(json.dumps(result)+'\n')
            with self.assertRaisesRegex(ValueError,'saved result differs'):
                audit(attempt,survey_path)


if __name__ == '__main__':
    unittest.main()
