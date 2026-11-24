import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT.parents[1]/'runtime'))
from entry_timing import ASSIGNMENT
from native_capture import capture
from analysis import run as run_analysis
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
            (attempt/'raw.mkv').write_bytes(video.read_bytes())
            negative = root/'negative'
            shutil.copytree(attempt, negative)
            (negative/'crossing-survey.json').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source: crossing-survey.json'):
                run_analysis(negative,negative/'analysis-report.json')
            shutil.copy2(attempt/'crossing-survey.json',negative/'crossing-survey.json')
            (negative/'original-trace.json').write_text(
                (negative/'original-trace.json').read_text().replace('inoperative','green',1))
            with self.assertRaisesRegex(ValueError, 'original trace digest differs'):
                run_analysis(negative,negative/'analysis-report.json')
            report = run_analysis(attempt,attempt/'analysis-report.json')
            from scenario_pipeline.worker_exchange.measurement_contract import validate, verify_report
            contract = json.loads((ROOT/'measurement-contract-precedence.json').read_text())
            plan = json.loads((ROOT/'case-plan.json').read_text())
            self.assertEqual(len(validate(contract,plan['requirement_dispositions'],
                                          (ROOT/'analysis.py').read_text(),case)),4)
            self.assertEqual(len(verify_report(contract,report,attempt)),4)
            changed = json.loads(json.dumps(report))
            changed['measurements']['crossing_context']['sources']['crossing-survey.json'] = '0'*64
            with self.assertRaisesRegex(ValueError,'Measurement source hash differs'):
                verify_report(contract,changed,attempt)
            self.assertEqual(report['measurements']['entry_time_difference_s']['method'],
                             'measure_entry_timing')
            self.assertFalse(report['physical_acceptance_claimed'])
            result_path = attempt/'result.json'
            result = json.loads(result_path.read_text())
            self.assertEqual(result['case_id'],case)
            self.assertFalse(result['setup_confirmed'])
            self.assertFalse(result['target_checks'][0]['matched'])
            from scenario_pipeline.batch_pipeline.validation import recording_evidence
            recording_evidence(result,result['recording_description'],lambda ref: attempt/ref)
            self.assertEqual(len(result['recording_evidence']),6)
            self.assertEqual(len((attempt/'channels/ego_body_history.jsonl').read_text().splitlines()),900)
            receipt = audit(attempt,survey_path)
            self.assertEqual(receipt['primary_video_decoded_frames'],900)
            self.assertFalse(receipt['physical_acceptance_claimed'])
            channel_path=attempt/'channels/governing_device_history.jsonl'
            original_channel=channel_path.read_text()
            channel_path.write_text(original_channel.replace('inoperative','green',1))
            with self.assertRaisesRegex(ValueError,'derived recording channel differs'):
                audit(attempt,survey_path)
            channel_path.write_text(original_channel)
            result['measured_values']['ego_minus_other_upper_entry_s'] = 99
            result_path.write_text(json.dumps(result)+'\n')
            with self.assertRaisesRegex(ValueError,'saved result differs'):
                audit(attempt,survey_path)


if __name__ == '__main__':
    unittest.main()
