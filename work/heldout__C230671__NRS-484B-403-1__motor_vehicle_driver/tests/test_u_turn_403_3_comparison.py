"""Independent frontage comparison rejects changed fixed conditions and source."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from audit_frontage_comparison import audit, read


class FrontageComparisonTests(unittest.TestCase):
    def test_current_fixed_condition_audit(self):
        result=audit()
        self.assertTrue(result['fixed_conditions_verified'])
        self.assertIsNone(result['business_district_legal_judgment'])

    def test_camera_or_original_building_tamper_rejected(self):
        candidate=copy.deepcopy(read('construction-prohibition_403_3.json'))
        config_item=next(item for item in candidate['files'] if item['path']=='config.json')
        config=json.loads(config_item['content'])
        config['cameras'][0]['width']+=1
        config_item['content']=json.dumps(config)
        with self.assertRaisesRegex(ValueError,'cameras differ'):
            audit(candidate=candidate)
        diagnostic=copy.deepcopy(read('diagnostic-prohibition_403_3.json'))
        source=json.loads(diagnostic['files']['u_turn_403_3_frontage.json'])
        source['built_frontage_candidate']['buildings'][0]['vertices_xy_m'][0][0]+=10
        source['built_frontage_candidate']['buildings'][0]['vertices_xy_m'][3][0]+=10
        diagnostic['files']['u_turn_403_3_frontage.json']=json.dumps(source)
        with self.assertRaisesRegex(ValueError,'source frontage differs'):
            audit(candidate_diagnostic=diagnostic)


if __name__=='__main__':
    unittest.main()
