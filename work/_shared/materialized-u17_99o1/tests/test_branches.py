import unittest,pathlib,json,importlib.util,sys,math
P=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(P))
spec=importlib.util.spec_from_file_location('local_scenario',P/'scenario.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class BranchTests(unittest.TestCase):
 def test_comparison_changes_only_declared_variables(self):
  cases=json.loads((P/'proposals/cases.json').read_text())['cases'][1:]
  for case in cases[1:]:
   actual={k for k in case['variable_assignments'] if case['variable_assignments'][k]!=cases[0]['variable_assignments'][k]}
   self.assertEqual(actual,set(case['deliberate_differences']))
 def test_route_fits_authored_paved_cross(self):
  c=json.loads((P/'config.json').read_text())
  for case in json.loads((P/'proposals/cases.json').read_text())['cases']:
   path=m.route(c,case)
   for i,(x,y) in enumerate(path[:-1]):
    theta=math.atan2(path[i+1][1]-y,path[i+1][0]-x)
    for dx,dy in [(-2.4,-1),(-2.4,1),(2.4,-1),(2.4,1)]:
     a=x+dx*math.cos(theta)-dy*math.sin(theta);b=y+dx*math.sin(theta)+dy*math.cos(theta)
     self.assertTrue(abs(a)<=7 or abs(b)<=7,(a,b))
 def test_no_samples_cannot_match_targets(self):self.assertEqual(m.target_checks({'variable_assignments':{}},[]),[])
 def test_actual_position_drives_target_check(self):
  case={'variable_assignments':{'commanded_approach_lateral_m':{'value':1.75}}}
  result=m.target_checks(case,[{'position_m':[-30,5.25,0]}])
  self.assertFalse(result[0]['matched']);self.assertEqual(result[0]['measured'],5.25)
