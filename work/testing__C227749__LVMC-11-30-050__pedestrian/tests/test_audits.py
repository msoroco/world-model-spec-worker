import importlib.util
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/(name+'.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

audit = load('delivery_audit')
pair = load('comparison_audit')

def scene(name): return json.loads((ROOT/'cases'/name/'scene.json').read_text())

class AuditTests(unittest.TestCase):
    def fixtures(self):
        rows=[{'frame':i+100,'time_s':i*.05,'source':'original_native','actor_id':7,
               'body_center_xy_m':[5,i]} for i in range(7)]
        joins=[{'frame':r['frame'],'time_s':r['time_s'],
                'cameras':{name:i for name in audit.CAMERAS}} for i,r in enumerate(rows)]
        cameras={name:{'kind':'original_native','sha256':'a'*64} for name in audit.CAMERAS}
        return rows,joins,cameras

    def test_saved_positive_and_missing_camera(self):
        rows, joins, cameras=self.fixtures()
        out=audit.audit_saved(scene('outside_right_angle'),rows,joins,cameras)
        self.assertEqual(out['original_frame_count'],7)
        del cameras['approach']
        with self.assertRaisesRegex(ValueError,'four exact camera'):
            audit.audit_saved(scene('outside_right_angle'),rows,joins,cameras)

    def test_saved_rejects_cadence_and_join(self):
        rows, joins, cameras=self.fixtures()
        rows[3]['time_s']+=.02
        with self.assertRaisesRegex(ValueError,'20 Hz'):
            audit.audit_saved(scene('outside_right_angle'),rows,joins,cameras)
        rows[3]['time_s']-=.02
        joins[3]['frame']+=1
        with self.assertRaisesRegex(ValueError,'join mismatch'):
            audit.audit_saved(scene('outside_right_angle'),rows,joins,cameras)

    def test_saved_rejects_non_original(self):
        rows, joins, cameras=self.fixtures()
        rows[2]['source']='requested_waypoint'
        with self.assertRaisesRegex(ValueError,'original Native'):
            audit.audit_saved(scene('outside_right_angle'),rows,joins,cameras)

    def test_comparison_pairs_and_unreviewed_change(self):
        a=scene('outside_right_angle'); b=scene('outside_neither')
        result=pair.audit_pair('right_angle_vs_neither',a,b)
        self.assertIn('route_xy_m',result['changed_fields'])
        b['opposite_curb_xy_m']=[[0,7],[10,7]]
        with self.assertRaisesRegex(ValueError,'unreviewed'):
            pair.audit_pair('right_angle_vs_neither',a,b)

    def test_crosswalk_exception_pair(self):
        a=scene('outside_neither');b=scene('inside_crosswalk_oblique')
        pair.audit_pair('outside_vs_crosswalk_exception',a,b)
        b['route_xy_m']=[[5,0],[5,6]]
        with self.assertRaisesRegex(ValueError,'unreviewed'):
            pair.audit_pair('outside_vs_crosswalk_exception',a,b)

    def test_shortest_endpoint_vs_detour_pair(self):
        a=scene('outside_shortest_endpoint'); b=scene('outside_endpoint_detour')
        out=pair.audit_pair('shortest_vs_neither',a,b)
        self.assertEqual(out['physical_realization'],'unconfirmed')
        self.assertEqual(a['route_xy_m'][0],b['route_xy_m'][0])

if __name__=='__main__': unittest.main()
