"""Author source-grounded draft proposals for C3997 solid-white crossing cases."""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
from outside_lane import CASES

HERE=Path(__file__).resolve().parent
AID=HERE.name
LAW='NRS-484B-587-2b'
CELL='C3997'
ACTOR='motor_vehicle_driver'
SOURCE='inputs/'+AID+'/assignment.json'
CAMERAS=tuple((name,1920 if i==0 else 1280,1080 if i==0 else 720)
              for i,name in enumerate(('overview','approach','reference_corner','driver_reference')))
CHANNELS=(
 ('controlled_access_authority','source record','separate public authority designation and access restriction'),
 ('public_highway_boundary','world meters','source-sealed public highway and controlled-access boundary'),
 ('lane_function','source record','traffic, marked entrance and exit lane roles from reviewed authority and map'),
 ('solid_white_separator','world meters','original solid white marking geometry and continuous identity'),
 ('vehicle_body_line_relation','world meters/frame','original bounding-box vertices and center signed distance to sourced separator'),
 ('vehicle_class_and_driver','source record','original actor blueprint and driving/control context'),
 ('emergency_necessity','source record','contemporaneous emergency record separate from requested route'),
 ('subsection3_shoulder_scope','source record','signed paved shoulder qualification, separately scoped from 2(b) crossing'),
)
RECORDING={'channels':[dict(name=n,unit=u,method=m,sampling_rate_hz=20,
   time_window='Full original 45-second 900-frame episode',
   reference_frame='Original CARLA world frame and source-sealed separator',
   uncertainty='Actual crossing, source validity and legal authorization need independent review')
   for n,u,m in CHANNELS],
 'context_inputs':[{'name':'reviewed_controlled_access_site','unit':'source record',
   'method':'separately hashed authority, map, lane functions, marking, driver and exception packet'}],
 'limitations':['Synthetic fixtures do not establish Native motion or legal status.',
   'A geometric crossing event is an observation, not a statutory numeric cutoff.']}
VARIABLES=('approach','origin','destination','vehicle_class',
           'emergency_required','subsection3_shoulder_authorized',
           'shoulder_paved','lawful_sign_permits_shoulder')

def put(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
 return {'path':str(path.relative_to(HERE)),'sha256':sha256(path.read_bytes()).hexdigest()}

def run():
 plan=json.loads((HERE/'case-plan.json').read_text())
 ids=[AID+'__'+c.name for c in CASES]
 if [c['case_id'] for c in plan['cases']]!=ids or len(plan['comparisons'])!=9:
  raise ValueError('C3997 exact case or comparison order changed')
 text=plan['law_text']
 for clause in ('Across any solid white line that separates an entrance or exit lane from a marked traffic lane.',
                'Except if required by an emergency','as otherwise authorized by subsection 3'):
  if clause not in text:raise ValueError('frozen law clause differs')
 refs=[dict(name=name,kind='world_setup',range_or_domain=domain,unit='source request')
   for name,domain in (
    ('approach','north or south original direction'),
    ('origin','marked traffic, entrance or exit lane'),
    ('destination','marked traffic, entrance or exit lane'),
    ('vehicle_class','ordinary motor vehicle or separately qualified subsection 3 vehicle'),
    ('emergency_required','contemporaneous emergency necessity absent or asserted'),
    ('subsection3_shoulder_authorized','separate signed paved shoulder qualification; no crossing permission assumed'))]
 refs.extend([dict(name=name,kind='world_setup',range_or_domain=domain,unit='source request')
   for name,domain in (
    ('shoulder_paved','independent paving source absent or present'),
    ('lawful_sign_permits_shoulder','lawfully placed qualifying shoulder sign absent or present'))])
 relevance={'cell_id':CELL,'actor':ACTOR,'status':'draft','relevant_laws':[{
   'law_id':LAW,'quote':'Across any solid white line that separates an entrance or exit lane from a marked traffic lane.',
   'applies_to':[ACTOR],'confidence':'medium','relevance_type':'specific_match',
   'notes':'Fixed adjacent_lanes, change_lane, solid_white_line; controlled-access and exception sources remain independent.'}],
   'borderline_excluded':[]}
 exceptions=[
  {'trigger':'Emergency necessity independently established from contemporaneous original source',
   'effect':'possible exception requiring review','replacement_obligation':'No automated legal conclusion',
   'source_clause':'Except if required by an emergency'},
  {'trigger':'Subsection 3 signed paved shoulder qualification independently established; scope does not itself authorize a solid-white crossing',
   'effect':'scope distinction requiring review','replacement_obligation':'No automated legal conclusion',
   'source_clause':'as otherwise authorized by subsection 3'}]
 template={'template_id':LAW+'@'+ACTOR,'law_id':LAW,'actor':ACTOR,'status':'draft','quote':text,
  'structure':{'law_id':LAW,'activation':{'condition':'A person drives on a separately established controlled-access highway.','numeric_conditions':[]},
    'obligation':{'description':'Do not drive across a solid white line separating a marked entrance or exit lane from a marked traffic lane.',
      'type':'must_not','numeric_conditions':[]},
    'exceptions':exceptions,'timing':{'description':'Original frame-by-frame body and marking history.','numeric_conditions':[]},
    'judgment_calls_needed':[]},'parameter_refs':refs}
 bindings={'cell_id':CELL,'actor':ACTOR,'status':'draft','established_contexts':[],
  'law_refs':[{'template_id':template['template_id'],'binding_kind':'direct'}],
  'context_refs':[],'fixed_parameters':[],
  'variable_parameters':[dict(r,used_by_laws=[LAW]) for r in refs]}
 selected=[]
 for c in CASES:
  assignments={n:{'kind':'world_setup',
    'value':getattr(c,n) if hasattr(c,n) else c.subsection3_shoulder_authorized,
    'unit':'source request'} for n in VARIABLES}
  primary='destination'
  if c.name.startswith('south_'):primary='approach'
  if 'to_traffic' in c.name:primary='origin'
  if c.emergency_required:primary='emergency_required'
  if c.subsection3_shoulder_authorized:primary='subsection3_shoulder_authorized'
  selected.append({'case_id':AID+'__'+c.name,'target_law_id':LAW,
   'target_type':'compliant_attempt' if c.origin==c.destination or c.emergency_required else 'violating_attempt',
   'status':'draft','rationale':'Requested route and context contrast only; physical crossing and legal treatment remain unresolved.',
   'variable_assignments':assignments,
   'unresolved_judgment_calls':['Controlled-access designation, separator continuity, emergency necessity and subsection 3 scope need independent review'],
   'recording_description':RECORDING,'paired_probe_id':'solid-white-crossing-controlled-comparisons',
   'deliberate_differences':list(VARIABLES),
   'probe':{'primary_variable':primary,'comparison_or_standard':'Nine exact source-bound plan comparisons',
            'target_value_or_branch':c.name}})
 baseline=dict(selected[0],case_id=AID+'__baseline',target_law_id=None,target_type='baseline')
 for key in ('paired_probe_id','deliberate_differences','probe'):baseline.pop(key)
 cases={'cell_id':CELL,'actor':ACTOR,'status':'draft','sweep_specs':[],
  'sweeps_expanded':True,'cases':[baseline]+selected}
 proposals=HERE/'proposals'
 stage={name:put(proposals/(name+'.json'),value) for name,value in
  [('relevance-batch',relevance),('relevance',relevance),('template',template),
   ('bindings',bindings),('cases',cases)]}
 put(proposals/'semantic-index.json',{'format':'worker-semantic-delivery',
  'assignment_id':AID,'status':'source_gated_draft',
  'stages':{'relevance_batch':stage['relevance-batch'],'relevance':stage['relevance'],
   'template':stage['template'],'judgment_observables':[],
   'bindings':stage['bindings'],'cases':stage['cases']}})
 requirements=[
  ('Controlled-access public highway and authority boundary','controlled_access_authority'),
  ('Marked traffic versus entrance/exit lane function','lane_function'),
  ('Fixed solid-white separator marking and placement','solid_white_separator'),
  ('Original vehicle body trajectory across or alongside separator','vehicle_body_line_relation'),
  ('Person driving and vehicle identity','vehicle_class_and_driver'),
  ('Emergency necessity and distinct subsection 3 shoulder scope','emergency_necessity')]
 plan['requirement_dispositions']=[dict(disposition_index=i,requirement=req,
  source=SOURCE,status='selected_required',case_ids=ids,
  evidence_or_gap='No accepted recording; source-sealed original Native and authority evidence required',
  planned_channel=channel) for i,(req,channel) in enumerate(requirements)]
 plan['source_observation_mapping']={}
 plan['observations']=[{'name':n,'unit':u,'method':m,
  'source':'original Native frames and separately sealed reviewed source packet','mandatory':True}
  for n,u,m in CHANNELS]
 plan['camera_plan']={'profile':'overview1080-capability','duration_s':45,
  'composition':'synchronized_four_view_primary','coverage':[
   {'view':n,'subject':'ego body, solid-white line, adjacent lane functions and crossing interval',
    'interval':'full 45-second original episode'} for n,_,_ in CAMERAS]}
 for item in plan['cases']:
  item['kind']='delivery';item['new_capture_selected']=True
  item['recording_description']=RECORDING
 plan['planning_status']='source_gated_draft_semantics_and_exact_cases'
 (HERE/'case-plan.json').write_text(json.dumps(plan,indent=2,ensure_ascii=False)+'\n')

if __name__=='__main__':run()
