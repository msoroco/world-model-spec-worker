"""Normalize the selected exact case proposals; disclose incomplete judgment grids."""
import json,hashlib
from pathlib import Path
r=Path(__file__).resolve().parent;p=r/'proposals';m=json.loads((r/'execution-manifest.json').read_text());aid=r.name;lid='NRS-484B-113-1';actor='motor_vehicle_driver'
original=json.loads((p/'cases.json').read_text())
rows=[]
base_desc=json.loads((r/m['cases'][0]['construction']).read_text())['recording_description']
assign=lambda spacing,policy:{'reverse_motion':{'kind':'subject_behavior','value':None},'other_traffic_spacing':{'kind':'world_setup','value':spacing},'other_traffic_speed_policy':{'kind':'world_setup','value':policy}}
rows.append({'case_id':aid+'__baseline_no_reverse','target_law_id':None,'target_type':'baseline','rationale':'Shared narrow-road context without backing; no legal outcome asserted.','variable_assignments':assign(12.0,'steady'),'recording_description':base_desc,'unresolved_judgment_calls':[]})
for e in m['cases']:
 slug=e['case_id'].rsplit('__',1)[-1];construction=json.loads((r/e['construction']).read_text())
 spacing,policy={'reverse_clear_traffic_steady':(12.0,'steady'),'reverse_close_traffic_steady':(7.0,'steady'),'reverse_clear_traffic_brakes':(10.4,'braking')}[slug]
 row={'case_id':e['case_id'],'target_law_id':lid,'target_type':'boundary_probe','rationale':{'reverse_clear_traffic_steady':'Measure clear spacing and steady traffic during original backing without a legal cutoff.','reverse_close_traffic_steady':'Measure closer spacing while holding original ego motion and traffic speed steady.','reverse_clear_traffic_brakes':'Measure traffic deceleration while retaining the measured minimum clearance of the clear steady comparison.'}[slug], 'variable_assignments':assign(spacing,policy),'recording_description':construction['recording_description'],'unresolved_judgment_calls':['reasonable safety','without interfering with other traffic'],'paired_probe_id':'traffic_clearance' if slug!='reverse_clear_traffic_brakes' else 'traffic_interference','deliberate_differences':['other_traffic_spacing'] if slug!='reverse_clear_traffic_brakes' else ['other_traffic_spacing','other_traffic_speed_policy'],'probe':{'primary_variable':'other_traffic_spacing' if slug!='reverse_clear_traffic_brakes' else 'other_traffic_speed_policy','comparison_or_standard':'physical contrast; legal judgment unresolved','target_value_or_branch':spacing if slug!='reverse_clear_traffic_brakes' else policy}}
 rows.append(row)
sweeps=[{'sweep_id':'backing-safety-physical-grid','target_law_id':lid,'judgment_refs':[{'phrase':'reasonable safety','note':'No statutory numeric safety cutoff.'}],'status':'incomplete','rationale':'A fixed physical sampling grid is required before canonical judgment coverage.','missing_inputs':['Exact controller sweep axes and complete Native feasibility evidence are not yet encoded in selected constructions.']}, {'sweep_id':'backing-interference-physical-grid','target_law_id':lid,'judgment_refs':[{'phrase':'without interfering with other traffic','note':'Traffic interference requires independent original-source observations.'}],'status':'incomplete','rationale':'A fixed traffic-response sampling grid is required before canonical judgment coverage.','missing_inputs':['Original other-speed response channel and complete Native feasibility evidence are not yet encoded in selected constructions.']}]
proposal={'format':'worker-cases-proposal','status':'draft','cell_id':'C136014','actor':actor,'sweep_specs':sweeps,'cases':rows,'sweeps_expanded':True}
(p/'cases.json').write_text(json.dumps(proposal,indent=2)+'\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
names={'relevance_batch':'relevance_batch.json','relevance':'relevance.json','template':'template.json','judgment_observables':['judgment_safety.json','judgment_interference.json'],'bindings':'bindings.json','cases':'cases.json'}
refs={}
for stage,value in names.items():
 if isinstance(value,list):refs[stage]=[{'path':'proposals/'+name,'sha256':sha(p/name)} for name in value]
 else:refs[stage]={'path':'proposals/'+value,'sha256':sha(p/value)}
(p/'semantic-index.json').write_text(json.dumps({'format':'worker-semantic-delivery','assignment_id':aid,'stages':refs},indent=2)+'\n')
print('canonical case draft and source-hashed semantic chain authored; judgment grids explicitly incomplete')
