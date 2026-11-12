"""Mapped-divider comparison rejects fixed-condition and geometry drift."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audit_divider_comparison import audit,read


class DividerComparisonTests(unittest.TestCase):
    def test_current_audit_retains_unknown_authority(self):
        result=audit()
        self.assertTrue(result['fixed_conditions_verified'])
        self.assertIsNone(result['divided_highway_legal_judgment'])

    def test_camera_and_median_tampering_rejected(self):
        candidate=copy.deepcopy(read('construction-prohibition_227.json'))
        item=next(row for row in candidate['files'] if row['path']=='config.json')
        config=json.loads(item['content'])
        config['cameras'][0]['height']+=1
        item['content']=json.dumps(config)
        with self.assertRaisesRegex(ValueError,'cameras differ'):
            audit(candidate=candidate)
        diagnostic=copy.deepcopy(read('diagnostic-prohibition_227.json'))
        source=json.loads(diagnostic['files']['u_turn_227_divider.json'])
        source['divider_candidate']['unoccupied_lane_edge_gap_m']=100
        diagnostic['files']['u_turn_227_divider.json']=json.dumps(source)
        with self.assertRaisesRegex(ValueError,'geometry differs'):
            audit(candidate_diagnostic=diagnostic)


if __name__=='__main__':unittest.main()
