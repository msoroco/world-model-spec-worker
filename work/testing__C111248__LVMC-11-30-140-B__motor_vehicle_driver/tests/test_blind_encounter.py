import importlib.util
from pathlib import Path
import unittest

P = Path(__file__).resolve().parents[1] / 'blind_encounter.py'
spec = importlib.util.spec_from_file_location('blind_encounter', P)
m = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class TestEncounter(unittest.TestCase):
    def setUp(self):
        self.att = {'person_actor_id': 5, 'source_sha256': 'a'*64}
        self.cue = {'person_actor_id': 5, 'source_sha256': 'b'*64, 'cue': 'white_cane'}
        self.route = [{'map_id':'Town','x':x,'y':0,'lane_id':1,'road_id':2} for x in (0,10,20)]
        self.pose = {'map_id':'Town','x':11,'y':2,'ground_z':0}

    def test_source_bound_plan(self):
        p=m.plan_native('white_full_stop_wait',map_id='Town',route_waypoints=self.route,pedestrian_pose=self.pose,blindness_attestation=self.att,cue_source=self.cue,driver_actor_id=4,pedestrian_actor_id=5)
        self.assertEqual(p['capture']['hz'],20)
        self.assertEqual(p['controller'],'brake_on_person_approach')
        with self.assertRaisesRegex(ValueError,'attestation'):
            m.plan_native('white_full_stop_wait',map_id='Town',route_waypoints=self.route,pedestrian_pose=self.pose,blindness_attestation={},cue_source=self.cue,driver_actor_id=4,pedestrian_actor_id=5)
        with self.assertRaisesRegex(ValueError,'does not approach'):
            m.plan_native('white_full_stop_wait',map_id='Town',route_waypoints=self.route,pedestrian_pose={**self.pose,'x':100},blindness_attestation=self.att,cue_source=self.cue,driver_actor_id=4,pedestrian_actor_id=5)

    def rows(self):
        return [{'frame':100+i,'time_s':i*.05,'person_actor_id':5,'driver_speed_mps':(0 if i in (2,3) else 2),'body_gap_m':10-i,'person_in_path':True,'person_clear':i>=4,'contact':False,'precaution':i>=4} for i in range(6)]

    def test_saved_measurements(self):
        r=m.measure_saved('white_full_stop_wait',self.rows(),attestation=self.att,cue_source=self.cue)
        self.assertEqual((r['first_stop_frame'],r['first_proceed_frame']),(102,104))
        self.assertTrue(r['person_clear_at_proceed'])
        self.assertTrue(r['precaution_at_proceed'])
        with self.assertRaisesRegex(ValueError,'original frames'):
            bad=self.rows(); bad[3]['frame']=120
            m.measure_saved('white_full_stop_wait',bad,attestation=self.att,cue_source=self.cue)
        with self.assertRaisesRegex(ValueError,'required original'):
            bad=self.rows(); bad[3].pop('contact')
            m.measure_saved('white_full_stop_wait',bad,attestation=self.att,cue_source=self.cue)

    def test_comparison(self):
        a=m.measure_saved('white_full_stop_wait',self.rows(),attestation=self.att,cue_source=self.cue)
        b={**a,'case_id':'white_roll_through'}
        self.assertTrue(m.audit_comparison(a,b,deliberate='response')['passed'])
        with self.assertRaisesRegex(ValueError,'fixed'):
            m.audit_comparison(a,{**b,'person_actor_id':6},deliberate='response')
        with self.assertRaisesRegex(ValueError,'undeclared case'):
            m.audit_comparison(a,{**b,'case_id':'red_tip_full_stop_wait'},deliberate='response')
        with self.assertRaisesRegex(ValueError,'missing'):
            m.audit_comparison(a,{},deliberate='response')

if __name__ == '__main__': unittest.main()

class TestNativeConstruction(unittest.TestCase):
    def setUp(self):
        self.plan = m.plan_native('white_full_stop_wait', map_id='Town',
            route_waypoints=[{'map_id':'Town','road_id':1,'lane_id':1,'x':0,'y':0},{'map_id':'Town','road_id':1,'lane_id':1,'x':10,'y':0}],
            pedestrian_pose={'map_id':'Town','x':10,'y':2,'ground_z':0},
            blindness_attestation={'person_actor_id':5,'source_sha256':'a'*64},
            cue_source={'person_actor_id':5,'source_sha256':'b'*64,'cue':'white_cane'},
            driver_actor_id=4,pedestrian_actor_id=5)

    def test_spawn_readback_and_rollback(self):
        class Adapter:
            def __init__(self, bad=False): self.bad=bad; self.deleted=[]; self.calls=[]
            def map_waypoint(self,*args): self.calls.append(('waypoint',args)); return object()
            def spawn_vehicle(self,wp): self.calls.append(('vehicle',wp)); return 4
            def spawn_pedestrian(self,pose): self.calls.append(('person',pose)); return 5
            def attach_cue(self,person,cue): self.calls.append(('cue',cue)); return 6
            def actor_readback(self,actor):
                return {'alive':True,'actor_id':actor,'cue':('wrong' if self.bad else 'white_cane') if actor==6 else None,'attached_to':5 if actor==6 else None}
            def destroy_actor(self,actor): self.deleted.append(actor)
        good=Adapter(); receipt=m.construct_native(good,self.plan)
        self.assertEqual(receipt['actors']['cue']['attached_to'],5)
        self.assertEqual(receipt['owned_handles'],(4,5,6))
        self.assertEqual([c[0] for c in good.calls],['waypoint','waypoint','vehicle','person','cue'])
        bad=Adapter(True)
        with self.assertRaisesRegex(ValueError,'cue attachment'):
            m.construct_native(bad,self.plan)
        self.assertEqual(bad.deleted,[6,5,4])
        class WrongPerson(Adapter):
            def spawn_pedestrian(self, pose): return 8
            def actor_readback(self, actor):
                row = super().actor_readback(actor)
                if actor == 6: row['attached_to'] = 8
                return row
        wrong=WrongPerson()
        with self.assertRaisesRegex(ValueError,'reviewed map source'):
            m.construct_native(wrong,self.plan)
        self.assertEqual(wrong.deleted,[6,8,4])
