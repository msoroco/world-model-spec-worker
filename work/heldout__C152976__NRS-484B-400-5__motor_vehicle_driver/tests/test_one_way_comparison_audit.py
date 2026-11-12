import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from one_way_comparison_audit import audit
import test_one_way_finalizer as source_fixture


def fixture(path,branch):
    source_fixture.SourceJoinTests().make_sources(path)
    cfg={'law_id':'NRS-484B-400-5','cell_id':'C152976','actor':'motor_vehicle_driver',
         'case_branch':branch,'selected_case_id':'heldout__C152976__NRS-484B-400-5__motor_vehicle_driver__'+branch,
         'site_source':'site.json','vehicle_blueprint_id':'vehicle.test','rate_hz':20,
         'duration_s':8,'frames':160,'cameras':['overview','approach','reference_corner','driver_reference'],
         'required_atoms':[],'source_packets':[],'target_speed_mps':5.,
         'lateral_scale':1.,'speed_kp':.22,'lookahead_m':3.,'overview_height_delta_m':0}
    (path/'config.json').write_text(json.dumps(cfg))
    rows=[json.loads(line) for line in (path/'native/footprints.jsonl').read_text().splitlines()]
    if branch=='approach_shifted_right':
        for point in rows[0]['body_corners_xy']:point[0]+=1
    if branch=='departure_shifted_right':
        for point in rows[-1]['body_corners_xy']:point[1]+=1
    (path/'native/footprints.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    return cfg


class ComparisonAuditTests(unittest.TestCase):
    def test_both_declared_differences_and_fixed_conditions(self):
        for comparison,branch in (('approach_left_edge','approach_shifted_right'),
                                  ('departure_left_edge','departure_shifted_right')):
            with self.subTest(comparison=comparison),TemporaryDirectory() as x,TemporaryDirectory() as y:
                a,b=Path(x),Path(y);fixture(a,'left_edge_reference');fixture(b,branch)
                result=audit(comparison,a,b)
                self.assertTrue(result['fixed_conditions_checked'])
                self.assertEqual(result['legal_practicability_judgment'],'unresolved')
                cfg=json.loads((b/'config.json').read_text());cfg['lookahead_m']=4
                (b/'config.json').write_text(json.dumps(cfg))
                with self.assertRaisesRegex(ValueError,'Fixed condition differs'):
                    audit(comparison,a,b)

    def test_rejects_unobserved_difference_and_changed_site(self):
        with TemporaryDirectory() as x,TemporaryDirectory() as y:
            a,b=Path(x),Path(y);fixture(a,'left_edge_reference');fixture(b,'approach_shifted_right')
            rows=[json.loads(line) for line in (b/'native/footprints.jsonl').read_text().splitlines()]
            for point in rows[0]['body_corners_xy']:point[0]-=1
            (b/'native/footprints.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with self.assertRaisesRegex(ValueError,'difference unobserved'):
                audit('approach_left_edge',a,b)
            for point in rows[0]['body_corners_xy']:point[0]+=1
            (b/'native/footprints.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            site=json.loads((b/'site.json').read_text());site['source_id']='different'
            (b/'site.json').write_text(json.dumps(site))
            with self.assertRaisesRegex(ValueError,'curb/site source binding'):
                audit('approach_left_edge',a,b)


if __name__=='__main__':unittest.main()
