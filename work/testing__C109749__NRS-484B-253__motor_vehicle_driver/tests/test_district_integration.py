import unittest
from unittest.mock import patch
import runner

class DistrictCaptureIntegration(unittest.TestCase):
    def test_exact_source_gate_is_invoked_and_diagnostic_rejected(self):
        context={'native_junction_id':17,'intersection_polygon_xy_m':[[0,0],[1,0],[1,1],[0,1]]}
        with self.assertRaisesRegex(ValueError,'packet path required'):
            runner.bind_district_context(dict(context),'Town01',None)
        with patch.object(runner,'verify_district_site_packet',return_value={'diagnostic_only':True}) as check:
            with self.assertRaisesRegex(ValueError,'Diagnostic district packet'):
                runner.bind_district_context(dict(context),'Town01','review.json')
            check.assert_called_once()
        reviewed={'diagnostic_only':False,'physical_district_verified':False,'legal_verdict_asserted':False}
        with patch.object(runner,'verify_district_site_packet',return_value=reviewed) as check:
            bound=runner.bind_district_context(dict(context),'Town01','review.json')
            self.assertEqual(bound['district_source_review'],reviewed)
            self.assertEqual(check.call_args.args[1:],('Town01','review.json'))
            self.assertEqual(check.call_args.args[0]['native_junction_id'],17)
