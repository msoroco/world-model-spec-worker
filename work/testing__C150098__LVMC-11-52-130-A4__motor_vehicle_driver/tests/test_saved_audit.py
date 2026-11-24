"""Hash and count rejection for synthetic original-shaped parking histories."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hydrant import ASSIGNMENT, CASES
from saved_audit import audit, sha


class SavedAuditTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.case=CASES[0]
        self.site={'assignment_id':ASSIGNMENT,'cell_id':'C150098','layout':'one_way_road',
            'control':'fire_hydrant','map_sha256':'map','municipal_jurisdiction_sha256':'city',
            'parallel_parking_authority_sha256':'permission','parallel_parking_permitted':True,
            'hydrant_identity_sha256':'hydrant','hydrant_geometry_sha256':'geometry',
            'hydrant_blueprint_sha256':'blueprint','curb_source_sha256':'curb',
            'one_way_direction_sha256':'direction','ego_blueprint_sha256':'vehicle',
            'camera_plan_sha256':'cameras','hydrant_physical_support':'spawned_prop',
            'hydrant':{'west_x_m':0.0,'east_x_m':.5,'curb_y_m':-2.0,'depth_m':.4},
            'approach_waypoints':[[-20,-2],[20,-2]],'property_status':'private',
            'sign_status':'absent','red_paint_status':'absent'}
        (self.root/'site.json').write_text(json.dumps(self.site))
        self.rows=[]
        for i in range(4):
            self.rows.append({'actor_id':11,'hydrant_actor_id':22,'map_sha256':'map',
                'site_sha256':sha(self.root/'site.json'),'hydrant_identity_sha256':'hydrant',
                'hydrant_geometry_sha256':'geometry','parallel_parking_authority_sha256':'permission',
                'camera_plan_sha256':'cameras','case_id':ASSIGNMENT+'__'+self.case.suffix,
                'frame':100+i,'time_s':i*.05,'hydrant_physically_present':True,
                'body_source_sha256':'body','frame_map_sha256':'frames',
                'body_west_x_m':-8.422,'body_east_x_m':-4.422,
                'activity_observation':'parked','exception_kind':'none'})
        self.write()

    def write(self):
        (self.root/'original-hydrant-history.jsonl').write_text(
            ''.join(json.dumps(row)+'\n' for row in self.rows))
        (self.root/'source-manifest.json').write_text(json.dumps({name:{
            'kind':'original_native','sha256':sha(self.root/name)}
            for name in ('site.json','original-hydrant-history.jsonl')}))

    def test_replay_saved_original(self):
        result=audit(self.root,self.case.suffix,frames=4)
        self.assertEqual(result['frame_count'],4)
        self.assertAlmostEqual(result['measurement']['minimum_longitudinal_gap_m'],4.422)
        self.assertFalse(result['legal_verdict_claimed'])

    def test_missing_stale_short_and_wrong_site_rejected(self):
        (self.root/'original-hydrant-history.jsonl').write_text('tampered')
        with self.assertRaisesRegex(ValueError,'missing or stale'):
            audit(self.root,self.case.suffix,frames=4)
        self.write();self.rows.pop();self.write()
        with self.assertRaisesRegex(ValueError,'frame count'):
            audit(self.root,self.case.suffix,frames=4)
        self.rows[0]['site_sha256']='bad';self.write()
        with self.assertRaisesRegex(ValueError,'site hash'):
            audit(self.root,self.case.suffix,frames=3)


if __name__=='__main__':unittest.main()
