import unittest,pathlib,sys,importlib.util
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
spec=importlib.util.spec_from_file_location('projection_runner',pathlib.Path(__file__).resolve().parents[1]/'runner.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class SightProjection(unittest.TestCase):
 def setUp(self):self.s=dict(actor_id=1,time_s=1,position_m=[1,2,0],heading_deg=0,speed_mps=4,body_vertices_m=[[0,1,0],[2,1,0]],native_lane={'road_id':1,'lane_id':-1},lamp_bits=0,blueprint='vehicle.tesla.model3')
 def project(self,event):return m.atom_measurements(['st.sight_distance'],self.s,[self.s],{},[],event)
 def test_missing_original_packet_fails(self):self.assertRaises(ValueError,self.project,None)
 def test_route_limit_fails(self):self.assertRaises(ValueError,self.project,{'visibility':{'required_lane_ids':[-1],'approaches':[{'lane_id':-1,'any_body_sight_horizon':{'bound':'route_limit','unknown':True}}]}})
 def test_complete_original_packet_is_preserved(self):
  visibility={'required_lane_ids':[-1],'approaches':[{'lane_id':-1,'any_body_sight_horizon':{'bound':'at_least','distance_m':230,'unknown':False}}]};self.assertEqual(self.project({'visibility':visibility})['st.sight_distance'],visibility)
 def test_stop_geometry_is_not_native_sign(self):self.assertRaises(ValueError,m.atom_measurements,['dev.stop_sign'],self.s,[self.s],{},[])
