"""Actual shared runtime guard regressions; fixture subprocess is CPU-only."""
import tempfile
import json
from pathlib import Path
import unittest
from unittest import mock
import test_saved_processing002 as support

class LegacyGuardTests(unittest.TestCase):
    def setup_case(self,root,diagnostic=False):
        helper=support.SavedProcessingTests()
        manifest,attempt,output=helper.fixture(root,kind='native',diagnostic=diagnostic)
        support.write(attempt/'capture/manifest.json',{'case_id':support.CID})
        data=json.loads(manifest.read_text());data['cases'][0]['native_construction_sha256']=support.sha(attempt/'construction.json');support.write(manifest,data)
        return helper,manifest,attempt,output

    def test_exact_native_hash_reaches_analysis_and_binds_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper,manifest,attempt,output=self.setup_case(Path(tmp))
            with mock.patch.object(support.saved,'_closure'):
                receipt=helper.run_saved(manifest,attempt,output)
            self.assertTrue(receipt['legacy_native_binding']['original_hash_matched'])
            self.assertFalse(receipt['legacy_native_binding']['explicit_diagnostic_exception'])
            self.assertFalse(receipt['legacy_native_binding']['actual_recording_audited'])

    def test_wrong_real_native_hash_rejected_before_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper,manifest,attempt,output=self.setup_case(Path(tmp))
            data=json.loads(manifest.read_text());data['cases'][0]['native_construction_sha256']='0'*64;support.write(manifest,data)
            before=support.tree(attempt)
            with self.assertRaisesRegex(ValueError,'construction hash differs'):
                helper.run_saved(manifest,attempt,output)
            self.assertEqual(before,support.tree(attempt));self.assertFalse((output/'v0001/analysis').exists())

    def test_each_embedded_identity_is_required_even_diagnostic(self):
        for file in ('config.json','capture/manifest.json'):
            with self.subTest(file=file),tempfile.TemporaryDirectory() as tmp:
                helper,manifest,attempt,output=self.setup_case(Path(tmp),diagnostic=True)
                data=json.loads((attempt/file).read_text())
                if file=='config.json':data['case']['case_id']='renamed_v7_case'
                else:data['case_id']='renamed_v7_case'
                support.write(attempt/file,data)
                with self.assertRaisesRegex(ValueError,'embedded case identity differs'):
                    helper.run_saved(manifest,attempt,output)

    def test_explicit_native_diagnostic_hash_exception_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper,manifest,attempt,output=self.setup_case(Path(tmp),diagnostic=True)
            data=json.loads(manifest.read_text());data['cases'][0]['native_construction_sha256']='0'*64;support.write(manifest,data)
            receipt=helper.run_saved(manifest,attempt,output)
            self.assertFalse(receipt['legacy_native_binding']['original_hash_matched'])
            self.assertTrue(receipt['legacy_native_binding']['explicit_diagnostic_exception'])
            self.assertTrue(json.loads(Path(receipt['result']).read_text())['diagnostic_fixture'])

    def test_v7_manifest_without_legacy_key_keeps_prior_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper=support.SavedProcessingTests();manifest,attempt,output=helper.fixture(Path(tmp))
            receipt=helper.run_saved(manifest,attempt,output)
            self.assertNotIn('legacy_native_binding',receipt)

if __name__=='__main__':unittest.main()
