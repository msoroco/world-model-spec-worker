import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'native'))
from cameras import camera_plan
from controller import EngineeringKnobs,PathController
from engineering import TRIGGERS,parameters
from geometry import STOP_X_M,check,route
from measure_entrance import entrance_overlap_m
from runner import seal_after_release


class AlleyDraftTests(unittest.TestCase):
    def test_both_routes_and_fallback_start(self):
        self.assertEqual(check()['roads'],[1,2])
        for suffix,stop in STOP_X_M.items():
            self.assertEqual(route(suffix)[-1][0],stop)
            self.assertEqual(route(suffix,-55)[0][0],-55)
            self.assertGreater(len(route(suffix,-55)),len(route(suffix)))

    def test_candidates_change_distinct_knobs_with_measured_triggers(self):
        for suffix in STOP_X_M:
            primary=parameters(suffix,'primary')
            variants=[parameters(suffix,name) for name in ('fallback1','fallback2','fallback3')]
            self.assertEqual(len({tuple(sorted(v.items())) for v in [primary]+variants}),4)
            self.assertEqual({k for k in variants[0] if variants[0][k]!=primary[k]},{'start_x_m'})
            self.assertEqual({k for k in variants[1] if variants[1][k]!=primary[k]},{'braking_start_m'})
            self.assertEqual({k for k in variants[2] if variants[2][k]!=primary[k]},{'camera_profile'})
            self.assertTrue(all(TRIGGERS[name]['metric'] and TRIGGERS[name]['failure_condition']
                                for name in TRIGGERS))

    def test_source_camera_invariants(self):
        standard=camera_plan('primary');wide=camera_plan('fallback3')
        self.assertEqual([c['name'] for c in standard],
                         ['overview','approach','reference_corner','driver_reference'])
        self.assertEqual([(c['width'],c['height']) for c in standard],
                         [(1920,1080),(1280,720),(1280,720),(1280,720)])
        self.assertEqual([(c['width'],c['height']) for c in wide],
                         [(c['width'],c['height']) for c in standard])
        self.assertGreater(wide[0]['fov_deg'],standard[0]['fov_deg'])
        self.assertGreater(wide[2]['xyz_m'][2],standard[2]['xyz_m'][2])

    def test_exact_polygon_overlap_and_nonoverlap(self):
        entrance=(-3,-4,3,0)
        centered=[(-2.6,-3.1),(-2.6,-.9),(2.6,-.9),(2.6,-3.1)]
        remote=[(x-12,y) for x,y in centered]
        self.assertAlmostEqual(entrance_overlap_m(centered,entrance),5.2)
        self.assertEqual(entrance_overlap_m(remote,entrance),0)
        # A slanted body may clip against the entrance without any vertex inside.
        slanted=[(-5,-3),(-4,-5),(5,-1),(4,1)]
        self.assertGreater(entrance_overlap_m(slanted,entrance),0)

    def test_unknown_proposals_rejected(self):
        with self.assertRaises(ValueError):parameters('missing','primary')
        with self.assertRaises(ValueError):camera_plan('fallback4')
        with self.assertRaises(ValueError):route('reference',-75)

    def test_observed_pose_controller_requests_braking_and_stop(self):
        points=route('contrast')
        knobs=EngineeringKnobs(target_speed_mps=5,final_brake_mps2=2.08,final_margin_m=0)
        controller=PathController(points,2.8,30,knobs)
        moving=controller.step(position_xy_m=(-20,-2),yaw_rad=0,speed_mps=5,dt_s=.05)
        near=controller.step(position_xy_m=(-3,-2),yaw_rad=0,speed_mps=4,dt_s=.05)
        stopped=controller.step(position_xy_m=(0,-2),yaw_rad=0,speed_mps=0,dt_s=.05)
        self.assertGreater(moving['requested_speed_mps'],near['requested_speed_mps'])
        self.assertEqual(stopped['requested_speed_mps'],0)
        self.assertTrue(stopped['hand_brake'])

    def test_native_seal_requires_full_capture_and_owner_closure(self):
        import json
        import tempfile
        cameras={name:0 for name in
                 ('overview','approach','reference_corner','driver_reference')}
        called=[]
        def fake_seal(output,**kwargs):
            called.append(kwargs)
            return {'sealed':True}
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'config.json').write_text(json.dumps({'case_id':'c10014-test'}))
            self.assertEqual(seal_after_release(directory,480,{'restored':True},None,
                                                cameras,seal=fake_seal),{'sealed':True})
            self.assertEqual(len(called),1)
            self.assertEqual(called[0]['encoder_exit_codes'],cameras)
            for frames,restoration,error,codes in (
                (479,{'restored':True},None,cameras),
                (480,{'restored':False},None,cameras),
                (480,{'restored':True},{'capture_error':'failed'},cameras),
                (480,{'restored':True},None,{**cameras,'overview':1}),
                (480,{'restored':True},None,{'overview':0}),
            ):
                with self.assertRaises(RuntimeError):
                    seal_after_release(directory,frames,restoration,error,codes,
                                       seal=fake_seal)
            self.assertEqual(len(called),1)


if __name__=='__main__':unittest.main()
