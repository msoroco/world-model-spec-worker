import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from comparison_audit import compare_verified
from entry_timing import ASSIGNMENT, measure
from test_entry_timing import survey, trace


class ComparisonAuditTests(unittest.TestCase):
    def evidence(self,suffix,ego,other,hold_other_until=None):
        case=ASSIGNMENT+'__'+suffix
        packet=trace(suffix,ego,other)
        if hold_other_until is not None:
            for row in packet['frames'][other+10:hold_other_until]:
                row['other']['body_vertices_xy_m'] = [[-.2,-.2],[.2,-.2],[.2,.2],[-.2,.2]]
        return case,{'case_id':case,'measured_values':measure(packet,survey())}

    def test_response_comparison_requires_measured_contrast_and_same_survey(self):
        first,a=self.evidence('precedence',75,60)
        second,b=self.evidence('advance',65,60)
        evidence={first:a,second:b}; hashes={first:'same',second:'same'}
        self.assertEqual(compare_verified('precedence_response',evidence,hashes)
                         ['legal_judgment'],'unresolved')
        with self.assertRaisesRegex(ValueError,'survey changed'):
            compare_verified('precedence_response',evidence,{first:'same',second:'changed'})
        with self.assertRaisesRegex(ValueError,'measured response contrast'):
            compare_verified('precedence_response',{first:a,second:{'case_id':second,
                'measured_values':a['measured_values']}},hashes)

    def test_three_timing_probes_require_measured_order(self):
        entries=[self.evidence('timing_below',50,100,180),
                 self.evidence('timing_inside',100,100,180),
                 self.evidence('timing_above',150,100,180)]
        evidence=dict(entries); hashes={case:'same' for case in evidence}
        self.assertIn('ordered',compare_verified('approximately_same_time_brackets',
                                                 evidence,hashes)['measured_difference'])
        cases=list(evidence)
        reordered=dict(evidence)
        reordered[cases[0]]={'case_id':cases[0],
                             'measured_values':evidence[cases[2]]['measured_values']}
        with self.assertRaisesRegex(ValueError,'measured bracket ordering'):
            compare_verified('approximately_same_time_brackets',reordered,hashes)


if __name__=='__main__':
    unittest.main()
