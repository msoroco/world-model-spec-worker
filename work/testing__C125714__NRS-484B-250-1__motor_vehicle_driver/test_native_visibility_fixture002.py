import importlib.util
from pathlib import Path
import unittest
OWN=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('visibility_fixture',OWN/'native_visibility_fixture002.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
class VisibilityDiagnostic(unittest.TestCase):
 def actors(self):return [{'actor_id':1,'position_m':[0,0,0],'body_vertices_m':[[0,0,0]]*8},{'actor_id':2,'position_m':[10,0,0],'body_vertices_m':[[9,(-1 if i%2 else 1),(0 if i<4 else 2)] for i in range(8)]}]
 def test_one_clear_vertex_is_visible_even_center_blocked(self):
  rows=[{'clear':False,'blockers':[{'label':'building'}]} for _ in range(9)];rows[0]={'clear':True,'blockers':[]};r=helper.construct_relations(self.actors(),1,{2:rows})[0]
  self.assertTrue(r['visible']);self.assertFalse(r['rays'][-1]['clear']);self.assertEqual(r['rays'][0]['observer_m'],[0,0,1.5])
 def test_center_only_rejected(self):
  with self.assertRaises(ValueError):helper.construct_relations(self.actors(),1,{2:[{'clear':False,'blockers':[{'label':'building'}]}]})
 def test_empty_inventory_rejected(self):
  with self.assertRaises(ValueError):helper.construct_relations(self.actors()[:1],1,{})
 def test_author_packet_actual_case(self):
  import json,tempfile
  root=next((OWN.parents[1]/'.runtime-work/update002/physical/testing__C24757__NRS-484B-250-4__motor_vehicle_driver').glob('*/complete_motion'))
  cfg=json.loads((root/'config.json').read_text());event=json.loads((root/'capture/evidence.jsonl').read_text().splitlines()[0]);row=json.loads((root/'interaction_history.jsonl').read_text().splitlines()[0]);packet=helper.author_packet(root,cfg,event,row)
  self.assertEqual(len(packet['participants']),3);self.assertEqual(len(packet['relations']),2)
  for relation in packet['relations']:self.assertTrue(relation['visible']);self.assertEqual(len(relation['rays']),9)
  self.assertEqual(packet['relations'][0]['rays'][-1]['blockers'],row['sight_ray']['hits'])
  self.assertEqual(packet['participants'][0]['position_m'],event['ego']['position_m'])
if __name__=='__main__':unittest.main()
