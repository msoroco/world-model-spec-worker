import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from entry_timing import ASSIGNMENT
import delivery_audit
import comparison_audit


class AuditCommandTests(unittest.TestCase):
    def scratch(self):
        base=ROOT.parents[1]/'.runtime-work'/'c125751-audit-tests'
        base.mkdir(parents=True,exist_ok=True)
        return tempfile.TemporaryDirectory(dir=base)

    def test_delivery_command_rejects_other_case_and_original_overwrite(self):
        with self.scratch() as temporary:
            root=Path(temporary)
            attempt=root/'attempt';attempt.mkdir()
            output=root/'delivery-receipt.json'
            case=ASSIGNMENT+'__precedence'
            with patch.object(delivery_audit,'audit',return_value={'case_id':case,'saved_sources_verified':True}):
                with self.assertRaisesRegex(ValueError,'exact case differs'):
                    delivery_audit.main(['--attempt',str(attempt),'--survey',str(root/'survey.json'),
                                         '--case',ASSIGNMENT+'__advance','--output',str(output)])
                self.assertFalse(output.exists())
                delivery_audit.main(['--attempt',str(attempt),'--survey',str(root/'survey.json'),
                                     '--case',case,'--output',str(output)])
                self.assertEqual(json.loads(output.read_text())['case_id'],case)
                with self.assertRaisesRegex(ValueError,'fresh audit output'):
                    delivery_audit.main(['--attempt',str(attempt),'--survey',str(root/'survey.json'),
                                         '--case',case,'--output',str(output)])
                with self.assertRaisesRegex(ValueError,'outside original attempt'):
                    delivery_audit.main(['--attempt',str(attempt),'--survey',str(root/'survey.json'),
                                         '--case',case,'--output',str(attempt/'audit.json')])

    def test_comparison_command_binds_each_case_and_original_hash(self):
        with self.scratch() as temporary:
            root=Path(temporary)
            ids=[ASSIGNMENT+'__precedence',ASSIGNMENT+'__advance']
            args=['--comparison','precedence_response']
            for i,case in enumerate(ids):
                attempt=root/('attempt'+str(i));attempt.mkdir()
                (attempt/'result.json').write_text(json.dumps({'case_id':case})+'\n')
                survey=root/('survey'+str(i)+'.json');survey.write_text('{}\n')
                args.extend(['--attempt',case+'='+str(attempt),'--survey',case+'='+str(survey)])
            output=root/'comparison-receipt.json'
            with patch.object(comparison_audit,'audit_comparison',return_value={
                    'comparison_id':'precedence_response','case_ids':ids,'physical_acceptance_claimed':False}):
                comparison_audit.main(args+['--output',str(output)])
                receipt=json.loads(output.read_text())
                self.assertEqual(set(receipt['attempt_result_sha256']),set(ids))
                self.assertEqual(set(receipt['survey_sha256']),set(ids))
                with self.assertRaisesRegex(ValueError,'fresh comparison output'):
                    comparison_audit.main(args+['--output',str(output)])
                with self.assertRaisesRegex(ValueError,'once per case'):
                    comparison_audit.main(args+['--attempt',ids[0]+'='+str(root/'attempt0'),
                                                '--output',str(root/'other.json')])

    def test_source_completion_checks_entries_exits_targets_and_decode(self):
        case=ASSIGNMENT+'__precedence'
        measurement={'entry_brackets':{'ego':{'frame':70},'other':{'frame':60}},
                     'exit_brackets':{'ego':{'frame':90},'other':{'frame':80}}}
        sources={'case_id':case,'source_integrity':'passed','entry_measurement':measurement,
                 'native_frames':900,'camera_frames':3600,'all_camera_pixels_decoded':True}
        result={'case_id':case,'target_checks':[
            {'target':'ego_minus_other_entry_s','matched':True},
            {'target':'ego_response','matched':True}]}
        check=delivery_audit.assess_source_completion(sources,result,900)
        self.assertTrue(check['source_completion_candidate'])
        self.assertFalse(check['physical_acceptance_claimed'])
        self.assertFalse(check['actual_pixel_visibility_reviewed'])
        self.assertFalse(delivery_audit.assess_source_completion(sources,result,899)
                         ['source_completion_candidate'])
        measurement['exit_brackets']['other']=None
        self.assertFalse(delivery_audit.assess_source_completion(sources,result,900)
                         ['source_completion_candidate'])
        with self.assertRaisesRegex(ValueError,'case or integrity differs'):
            delivery_audit.assess_source_completion(sources,{**result,'case_id':ASSIGNMENT+'__advance'},900)


if __name__=='__main__':
    unittest.main()
