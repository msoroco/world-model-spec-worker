import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from traffic_spec_adapter.adapter import original_participants,attach_original_participants
class OriginalParticipantTests(unittest.TestCase):
 def fixture(self):
  vertices=[[x,y,z] for x in(3.,7.) for y in(1.,3.) for z in(0.,2.)]
  actor={'actor_id':2,'blueprint':'vehicle.lincoln.mkz_2020','speed_mps':5.,'velocity_mps':[3.,4.,0.],'heading_deg':0.,'body_vertices_m':vertices}
  ego=dict(actor,actor_id=1)
  evidence=[{'original_frame':10,'recording_time_s':.05,'actor_id':1,'ego':{'speed_mps':5.}}]
  row={'time_s':.05,'value':{'frame':10,'ego':ego,'other':actor,'commands':{'ego':100.,'other':100.}}}
  return row,evidence
 def read(self,row,evidence,acquisition='original_live_run'):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'motion.jsonl';p.write_text(json.dumps(row)+'\n');return original_participants(p,evidence,acquisition)
 def test_actual_motion_including_track_outside_crop(self):
  row,e=self.fixture();actors=self.read(row,e)[10];users=[{'track':1,'kin':{}}];footprints={}
  with patch('traffic_spec_adapter.adapter.classes',return_value=(['motor_vehicle'],[])):
   attach_original_participants(users,footprints,actors,1,Path('/unused'))
  self.assertEqual(users[1]['track'],2);self.assertEqual(users[1]['kin']['speed'],5.)
  self.assertEqual(users[1]['kin']['velocity'],[3.,-4.]);self.assertEqual(users[1]['kin']['position'],[5.,-2.]);self.assertNotIn('relations',users[1]);self.assertEqual(footprints[2].area,8.)
 def test_missing_or_wrong_frame_and_replay_rejected(self):
  row,e=self.fixture()
  for acquisition in('recorder_replay',None):
   with self.assertRaises(ValueError):self.read(row,e,acquisition)
  for bad in (dict(e[0],original_frame=11),dict(e[0],recording_time_s=.1)):
   with self.assertRaises(ValueError):self.read(row,[bad])
  with self.assertRaises(ValueError):self.read(row,e+[dict(e[0],original_frame=11)])
 def test_inconsistent_speed_or_duplicate_actor_rejected(self):
  row,e=self.fixture();bad=copy.deepcopy(row);bad['value']['other']['speed_mps']=6.
  with self.assertRaises(ValueError):self.read(bad,e)
  bad=copy.deepcopy(row);bad['value']['other']['actor_id']=1
  with self.assertRaises(ValueError):self.read(bad,e)
 def test_disagreement_with_native_geometry_rejected(self):
  row,e=self.fixture();actors=self.read(row,e)[10]
  users=[{'track':1,'kin':{}},{'track':2,'kin':{'position':[500.,-2.]}}]
  with self.assertRaises(ValueError):attach_original_participants(users,{},actors,1,Path('/unused'))
