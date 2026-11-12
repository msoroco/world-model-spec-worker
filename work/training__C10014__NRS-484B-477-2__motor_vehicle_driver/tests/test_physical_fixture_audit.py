"""Shape tests only; no result here is a Native physical proof."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from physical_fixture_audit import check_result


class PhysicalFixtureAuditTests(unittest.TestCase):
    def shaped_result(self, status, native=True):
        return {'case_id':'unit-case',
                'provenance_kind':'native' if native else 'synthetic_local_diagnostic',
                'diagnostic_fixture':not native,
                'accepted':False,'legal_verdict_claimed':False,
                'maneuver_completed':status=='met',
                'realized_observables':{'sampled_stopped_entrance_overlap':
                                        {'value':5.2,'reference':'native_samples.jsonl'}},
                'physical_checks':{'maneuver':{'status':status,
                    'method':'source-shaped unit test, not a Native observation',
                    'sources':{'native_samples.jsonl':'unit-source-hash'}}}}

    def test_three_expected_branches_and_mismatches(self):
        for kind,status in [('complete_motion','met'),
                            ('incomplete_motion','not_met'),
                            ('missing_evidence','unverified')]:
            with self.subTest(kind=kind):
                result=self.shaped_result(status)
                self.assertEqual(check_result(result,kind,'unit-case')['status'],status)
                with self.assertRaisesRegex(ValueError,'status'):
                    check_result(result,'complete_motion' if kind!='complete_motion'
                                 else 'incomplete_motion','unit-case')

    def test_synthetic_or_unsupported_completion_rejected(self):
        synthetic=self.shaped_result('met',native=False)
        with self.assertRaisesRegex(ValueError,'Synthetic'):
            check_result(synthetic,'complete_motion','unit-case')
        native=self.shaped_result('met')
        native['realized_observables']={}
        with self.assertRaisesRegex(ValueError,'realized Native'):
            check_result(native,'complete_motion','unit-case')
        native=self.shaped_result('not_met')
        native['maneuver_completed']=True
        with self.assertRaisesRegex(ValueError,'status'):
            check_result(native,'incomplete_motion','unit-case')


if __name__=='__main__':unittest.main()
