import json,pathlib,copy
R=pathlib.Path.cwd();ids=json.loads((R/'partitions/demo-test-01.json').read_text())['assignment_ids']
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
for aid in ids:
 w=R/'work'/aid;run=(w/'runner.py').read_text()
 run=run.replace('streams=[];samples=[];others=[];halt_start=None','streams=[];samples=[];others=[];halt_start=None;collisions=[]')
 run=run.replace("cap=PipelineCapture(client,ego,out,case['case_id'],required_observations=c['required_atoms'])","""cap=PipelineCapture(client,ego,out,case['case_id'],required_observations=c['required_atoms'])
        collision=world.spawn_actor(world.get_blueprint_library().find('sensor.other.collision'),carla.Transform(),attach_to=ego);actors.append(collision)
        collision.listen(lambda event:collisions.append(dict(frame=event.frame,other_actor_id=event.other_actor.id)))""")
 run=run.replace("result['target_checks']=target_checks(case,samples)","result['target_checks']=target_checks(case,samples)\n        if collisions:result['physical_failure_flags'].append('collision')\n        (out/'collisions.json').write_text(json.dumps(collisions))")
 run=run.replace("for actor in reversed(actors):\n            if hasattr(actor,'stop'):actor.stop()\n            actor.destroy()\n        world.apply_settings(old)","""for actor in reversed(actors):
            try:
                if hasattr(actor,'stop'):actor.stop()
                actor.destroy()
            except Exception as cleanup_error:result['physical_failure_flags'].append('actor_cleanup: '+str(cleanup_error))
        try:world.apply_settings(old)
        except Exception as cleanup_error:result['physical_failure_flags'].append('settings_restore: '+str(cleanup_error))""")
 (w/'runner.py').write_text(run)
 test='''import unittest,pathlib,json,importlib.util,sys,math
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
'''
 (w/'tests/test_branches.py').write_text(test)
 c=json.loads((w/'config.json').read_text());p=json.loads((w/'proposals/cases.json').read_text());bindings=json.loads((w/'proposals/bindings.json').read_text())
 bindings['established_contexts']=[dict(name='authored_context',source='explicit synthetic assumptions in case world_setup; operational realization remains partial')];bindings['law_refs']=[dict(template_id=c['law_id']+'@'+c['actor'],binding_kind='direct')];bindings['context_refs']=[]
 # All case variables are registered, retaining observed quantities separately.
 vars={k:v for case in p['cases'] for k,v in case['variable_assignments'].items()};bindings['variable_parameters']=[dict(name=k,kind=v['kind'],range_or_domain=sorted({str(case['variable_assignments'].get(k,{}).get('value')) for case in p['cases']}),used_by_laws=[c['law_id']]) for k,v in vars.items()];dump(w/'proposals/bindings.json',bindings)
 template=json.loads((w/'proposals/template.json').read_text());template['parameter_refs']=[dict(name=v['name'],kind=v['kind'],range_or_domain=v['range_or_domain']) for v in bindings['variable_parameters']];dump(w/'proposals/template.json',template)
 jud=[]
 for entry in template['structure']['judgment_calls_needed']:
  jud.append(dict(template_id=template['template_id'],phrase=entry['phrase'],note=entry['note'],status='draft',observable_requirements=dict(observables=[dict(name=a,unit='raw',description='Original native geometry or observed participant/device histories required by the supplied summary') for a in c['required_atoms']],context_inputs=[dict(name='authored_context',unit='object',description='Externally authored factual assumptions distinguished from observed scene data')],sweep_dimensions=[dict(name='commanded_approach_speed',unit='m/s',description='Physical controller target, distinct from observed speed and any legal standard')],landmarks=[],recording_needs=[dict(name='trace',unit='raw',description='Full original synchronized history')],limitations=['No numerical interpretation or judgment verdict','Native realization and mandatory atom projections remain partial'])))
 dump(w/'proposals/judgment-observables.json',jud)
 relevance=dict(cell_id=c['cell_id'],actor=c['actor'],status='draft',relevant_laws=[dict(law_id=c['law_id'],quote=template['quote'],applies_to=[c['actor']],relevance_type='specific_match',confidence='medium',notes='Assigned law only; exact activation and witness contexts retained. No additional legal overlays selected.')],borderline_excluded=[]);dump(w/'proposals/relevance.json',relevance)
 con=json.loads((w/'construction.json').read_text());con['files']=[dict(path=x,content=(w/x).read_text()) for x in ['runner.py','scenario.py','config.json','road-template.xodr']];dump(w/'construction.json',con)
 for case in p['cases'][2:]:
  cc=copy.deepcopy(con);cc['case_id']=case['case_id'];cfg=copy.deepcopy(c);cfg['default_case_id']=case['case_id'];next(f for f in cc['files'] if f['path']=='config.json')['content']=json.dumps(cfg,indent=2)+'\n';dump(w/'constructions'/(case['case_id']+'.json'),cc)
