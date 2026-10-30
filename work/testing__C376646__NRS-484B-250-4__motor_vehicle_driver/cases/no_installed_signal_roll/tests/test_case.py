import unittest,tempfile,pathlib,json,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import analyze
class TestMeasurement(unittest.TestCase):
 def test_exact_measurement(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t)
   (p/'signal_context.json').write_text(json.dumps({'intersection_polygon_xy_m':[[-7,-7],[7,-7],[7,7],[-7,7]],'reference_line_x_m':-11}))
   rows=[{'frame':i,'time_s':i*.05,'states':{'ego':{'body_vertices_m':[[x,0,0],[x+1,1,1]],'speed_mps':0 if i==0 else 4}}} for i,x in enumerate([-15,-5])]
   (p/'interaction_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
   self.assertTrue(analyze.stop_before_entry(p)['sampled_halt_precedes_entry'])
   rows[0]['states']['ego']['speed_mps']=4
   (p/'interaction_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
   self.assertFalse(analyze.stop_before_entry(p)['sampled_halt_precedes_entry'])

 def test_nearest_clear(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t)
   r={'frame':1,'time_s':.05,'sight_ray':{'hits':[{}],'eye_m':[-12,0,1.5]},'sight_candidates':[{'eye_m':[-12,0,1.5],'hit_count':1,'clear':False,'distance_to_intersection_m':5},{'eye_m':[-9,0,1.5],'hit_count':0,'clear':True,'distance_to_intersection_m':2},{'eye_m':[-8,0,1.5],'hit_count':0,'clear':True,'distance_to_intersection_m':1}]}
   (p/'interaction_history.jsonl').write_text(json.dumps(r)+'\n')
   self.assertEqual(analyze.sight_obstruction(p)['nearest_sampled_clear_point']['eye_m'][0],-8)

 def test_actual_authored_reference_geometry(self):
  import runner,xml.etree.ElementTree as ET
  cfg=json.loads(pathlib.Path(runner.ROOT/'config.json').read_text());cfg['reference_kind']='unmarked_crosswalk'
  tree=ET.fromstring(runner.authored_scene(cfg))
  self.assertGreaterEqual(len(tree.findall('.//lane[@type="sidewalk"]')),8)
  self.assertFalse(tree.findall('.//object[@name="StopLine"]'))
  cfg['installed_heads']=False
  self.assertFalse(ET.fromstring(runner.authored_scene(cfg)).findall('.//signal'))
