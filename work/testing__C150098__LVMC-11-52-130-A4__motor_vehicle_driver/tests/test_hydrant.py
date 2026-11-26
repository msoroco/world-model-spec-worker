"""CPU adapter and original-shaped history tests; no physical/legal claim."""
import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('c150098_hydrant',ROOT/'hydrant.py')
m=importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name]=m
spec.loader.exec_module(m)


def site():
    return {'assignment_id':m.ASSIGNMENT,'cell_id':'C150098','layout':'one_way_road',
            'control':'fire_hydrant','map_sha256':'map','municipal_jurisdiction_sha256':'city',
            'parallel_parking_authority_sha256':'permission','parallel_parking_permitted':True,
            'hydrant_identity_sha256':'hydrant','hydrant_geometry_sha256':'geometry',
            'hydrant_blueprint_sha256':'blueprint','curb_source_sha256':'curb',
            'one_way_direction_sha256':'direction','ego_blueprint_sha256':'vehicle',
            'camera_plan_sha256':'cameras','hydrant_physical_support':'spawned_prop',
            'hydrant':{'west_x_m':0.0,'east_x_m':.5,'curb_y_m':-2.0,'depth_m':.4},
            'approach_waypoints':[[-20,-2],[20,-2]],'property_status':'private',
            'sign_status':'absent','red_paint_status':'absent'}


class Adapter:
    def __init__(self):self.calls=[];self.destroyed=[];self.fail=None
    def spawn_hydrant(self,*args,**kwargs):self.calls.append('spawn_hydrant');return object()
    def lookup_hydrant(self,*args):self.calls.append('lookup_hydrant');return object()
    def read_hydrant(self,*args):self.calls.append('read_hydrant');return {
        'identity_sha256':'hydrant','geometry_sha256':'geometry',
        'physically_present':self.fail!='readback'}
    def spawn_vehicle(self,*args,**kwargs):self.calls.append('spawn_vehicle');return object()
    def set_route(self,*args,**kwargs):self.calls.append('set_route')
    def set_curb_target(self,*args,**kwargs):self.calls.append('set_curb_target')
    def set_exception_source(self,*args,**kwargs):self.calls.append('set_exception_source')
    def destroy(self,obj):self.destroyed.append(obj)


class HydrantTest(unittest.TestCase):
    def test_boundary_both_sides_and_private_unpainted(self):
        p=site();m.validate_site(p)
        for side in ('upstream','downstream'):
            cases=[c for c in m.CASES if c.side==side and c.activity=='park']
            gaps=[c.gap_m for c in cases]
            self.assertTrue(any(x<m.FEET_15_M for x in gaps))
            self.assertIn(m.FEET_15_M,gaps)
            self.assertTrue(any(x>m.FEET_15_M for x in gaps))
            for c in cases:
                interval=m.target_interval(p,c,4)
                observed_side,gap=m.gap(*interval,0,.5)
                self.assertEqual(observed_side,side)
                self.assertAlmostEqual(gap,c.gap_m)
        self.assertEqual(p['sign_status'],'absent')
        self.assertEqual(p['property_status'],'private')

    def test_physical_fixture_created_and_read_back(self):
        a=Adapter();case=m.CASES[0]
        result=m.build_case(a,site(),case,4)
        self.assertEqual(result['case_id'],m.ASSIGNMENT+'__'+case.suffix)
        self.assertEqual(a.calls,['spawn_hydrant','read_hydrant','spawn_vehicle',
                                  'set_route','set_curb_target'])
        a=Adapter();a.fail='readback'
        with self.assertRaisesRegex(ValueError,'readback'):
            m.build_case(a,site(),case,4)
        self.assertEqual(len(a.destroyed),1)

    def test_mapped_hydrant_and_exception_source(self):
        p=site();p['hydrant_physical_support']='map_object'
        p['police_direction_source_sha256']='police-source'
        c=next(c for c in m.CASES if c.exception=='police_direction')
        a=Adapter();m.build_case(a,p,c,4)
        self.assertIn('lookup_hydrant',a.calls)
        self.assertIn('set_exception_source',a.calls)
        del p['police_direction_source_sha256']
        with self.assertRaisesRegex(ValueError,'police_direction source'):
            m.build_case(Adapter(),p,c,4)

    def test_authority_and_one_way_direction_required(self):
        p=site();p['parallel_parking_permitted']=False
        with self.assertRaisesRegex(ValueError,'permission'):
            m.validate_site(p)
        p=site();p['approach_waypoints'].reverse()
        with self.assertRaisesRegex(ValueError,'direction'):
            m.validate_site(p)

    def test_original_body_gap_and_activity(self):
        p=site();c=m.CASES[0]
        fixed={'actor_id':11,'hydrant_actor_id':22,'map_sha256':'map','site_sha256':'site',
               'hydrant_identity_sha256':'hydrant','hydrant_geometry_sha256':'geometry',
               'parallel_parking_authority_sha256':'permission','camera_plan_sha256':'cameras'}
        rows=[]
        for i in range(4):
            rows.append(dict(fixed,case_id=m.ASSIGNMENT+'__'+c.suffix,frame=100+i,
                time_s=i*.05,hydrant_physically_present=True,
                body_source_sha256='body',frame_map_sha256='frames',
                body_west_x_m=-8.422,body_east_x_m=-4.422,
                activity_observation='parked',exception_kind='none'))
        result=m.measure_original_history(rows,p,c)
        self.assertAlmostEqual(result['minimum_longitudinal_gap_m'],4.422)
        self.assertEqual(result['legal_distance_convention'],'unresolved_review')
        rows[2]['body_east_x_m']=-3.0
        result=m.measure_original_history(rows,p,c)
        self.assertAlmostEqual(result['minimum_longitudinal_gap_m'],3.0)
        rows[2]['frame']+=1
        with self.assertRaisesRegex(ValueError,'frame/time identity'):
            m.measure_original_history(rows,p,c)

    def test_startup_transient_is_not_boundary_witness(self):
        p=site();c=m.CASES[0]
        fixed={'actor_id':11,'hydrant_actor_id':22,'map_sha256':'map','site_sha256':'site',
               'hydrant_identity_sha256':'hydrant','hydrant_geometry_sha256':'geometry',
               'parallel_parking_authority_sha256':'permission','camera_plan_sha256':'cameras'}
        rows=[]
        for i in range(3):
            rows.append(dict(fixed,case_id=m.ASSIGNMENT+'__'+c.suffix,frame=100+i,
                time_s=i*.05,hydrant_physically_present=True,
                body_source_sha256='body',frame_map_sha256='frames',
                body_west_x_m=-8.422 if i else -4,body_east_x_m=-4.422 if i else 0,
                activity_observation='parked' if i else 'moving',exception_kind='none'))
        measured=m.measure_original_history(rows,p,c)
        self.assertAlmostEqual(measured['minimum_longitudinal_gap_m'],4.422)
        self.assertEqual(measured['target_frame_count'],2)
        for row in rows:
            row['activity_observation']='moving'
        with self.assertRaisesRegex(ValueError,'target-side activity'):
            m.measure_original_history(rows,p,c)


if __name__=='__main__':unittest.main()
