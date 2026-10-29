"""Bind exact statutory text to complete law-specific measured output aggregates."""
import json,pathlib,importlib.util,re
ROOT=pathlib.Path(__file__).resolve().parents[2]
p=ROOT/'work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/package_builder.py';s=importlib.util.spec_from_file_location('b',p);b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
ids=json.loads((ROOT/'partitions/demo-test-02.json').read_text())['assignment_ids'];ids += [r['assignment_id'] for r in json.loads((ROOT/'work'/ids[0]/'additional-bindings.json').read_text())]
for aid in ids:
 folder=ROOT/'work'/aid;spec=json.loads((folder/'package-spec.json').read_text());ap=ROOT/'inputs'/aid/'assignment.json'
 if not ap.exists():ap=folder/'assignment.json'
 a=json.loads(ap.read_text());analysis=spec['analysis'];run=spec['runner']
 # Preserve all existing law-specific functions; combine actual measured outputs rather than choosing one fragment.
 methods=[]
 for m in spec['dispositions']:
  name=m['measurement']['method']
  if name not in methods:methods.append(name)
 aggregate='''def statutory_observations(p):
    return {'''+','.join(repr(name)+':'+name+'(p)' for name in methods)+'''}

def selected_scope_context(p):
    return {'authored_scope':p['scope_context'],'recorded_context':{k:v for k,v in p.items() if k not in ('motion_rows','trajectory','path_rows','indicator_rows','velocity_rows','scope_context')},'no_legal_scope_acceptance':True}

'''
 analysis=analysis.replace('def finalize(root,output):',aggregate+'def finalize(root,output):')
 # All seed finalizers have these final measurement assignments before report creation.
 loc=analysis.index('    report=')
 analysis=analysis[:loc]+"    measurements['complete_statutory_observations']={'method':'statutory_observations','value':statutory_observations(p),'sources':{'case_observation.json':h}}\n    measurements['selected_scope_context']={'method':'selected_scope_context','value':selected_scope_context(p),'sources':{'case_observation.json':h}}\n"+analysis[loc:]
 # 413 has combined distance/continuity/district observations rather than an arbitrary full-law/path-only join.
 if a['law_id']=='NRS-484B-413-2':
  analysis=analysis.replace("if remaining>=p.get('threshold_ft',100)*.3048:break", "if remaining>=p.get('threshold_ft',100)*.3048:\n            start=min(start+1,len(rows)-1);break")
  analysis=analysis.replace("'last_100ft_sampled_distance_m':remaining", "'last_100ft_sampled_distance_m':remaining,'reference_is_engineering_onset':True,'distance_window_bracket_m':[max(0,remaining-(segments[start-1] if start else 0)),remaining]")
 scope={'highway_designation':'Authored synthetic public highway; independent factual/legal jurisdiction review required','vehicle_blueprint':'vehicle.lincoln.mkz_2020','controller_scope':'Physical throttle/brake/steering commands on conventional vehicle; no automated-driving-system legal inference','cell_identity':a['cell_id'],'fixed_layout':a['cell']['layout'],'fixed_maneuver':a['cell']['maneuver'],'fixed_control':a['cell']['control'],'source':'Exact case config plus authored OpenDRIVE; actual public dedication/driver identity is not established by CPU fixture'}
 match=re.search(r'^(\s*)\(out/\'case_observation.json\'\)\.write_text\(json.dumps\((packet|obs),',run,re.M)
 assert match,aid
 indent=match.group(1).split('\n')[-1];var=match.group(2);pos=match.start()+len(match.group(1))-len(indent)
 run=run[:pos]+indent+var+"['scope_context']="+repr(scope)+'\n'+run[pos:]
 for case in spec['cases']:case['fixture']['case_observation.json']['scope_context']=scope
 spec.update(runner=run,analysis=analysis,dispositions=[dict(requirement=a['law']['text'],source=a['law']['source'],evidence_or_gap='Complete original law-specific geometry, trajectories, control and signal/environment measurements are returned together. Factual scope and legal judgments remain separate limitations.',measurement=dict(output_key='complete_statutory_observations',method='statutory_observations',kind='measured',value_type='object',inputs=['case_observation.json'])),dict(requirement='Selected witness source context: '+'; '.join(a['witness']['required_context']),source='assignment.witness.required_context',evidence_or_gap='Exact authored highway/vehicle/controller/cell scope and recorded context retained as sourced context; no factual legal acceptance asserted. Physical observations also appear in complete_statutory_observations.',measurement=dict(output_key='selected_scope_context',method='selected_scope_context',kind='sourced_context',value_type='object',inputs=['case_observation.json']))])
 b.write(folder/'package-spec.json',spec);b.build(spec)
 plan=json.loads((folder/'case-plan.json').read_text())
 if not (ROOT/'inputs'/aid/'assignment.json').exists():
  for m in plan['source_observation_mapping'].values():m['source_refs']=[str(ap.relative_to(ROOT))]
 b.write(folder/'case-plan.json',plan)
print('refined',len(ids),'packages')
