"""Resolve explicit delivery definitions without changing consumed requests."""
import hashlib,json
from copy import deepcopy
from pathlib import Path
from batch_pipeline.store import atomic

def resolve(case,default):
 return json.loads(Path(case['definition_file']).read_text()) if case.get('definition_file') else default

def document_single_lane(output):
 index=json.loads((output/'delivery_index.json').read_text())
 for entry in index['cells']:
  for case in entry['cases']:
   if case['case_id']!='C245490-223-1b-lanes-below' or case['status']!='validated':continue
   source=output.parent/case.get('definition_run_id',entry.get('run_id',index['run_id']))/'cells'/entry['cell_id']/'motor_vehicle_driver/cases.json'
   value=deepcopy(next(c for c in json.loads(source.read_text())['cases'] if c['case_id']==case['case_id']))
   attempt=Path(case['execution']);config=json.loads((attempt/'config.json').read_text());result=json.loads((attempt/'result.json').read_text())
   if not(config.get('applicability_negative_single_lane') and config['lane_count']==1 and result.get('measured_values',{}).get('straight_travel_completion_observed')):raise ValueError('Unconfirmed single-lane construction override')
   value['source_definition']={'path':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'original_consumed_request_preserved':True}
   value['construction_override']={'config':str(attempt/'config.json'),'sha256':hashlib.sha256((attempt/'config.json').read_bytes()).hexdigest(),'reason':'Explicit applicability-negative context; an adjacent-lane change has no destination on this one-lane map.'}
   value['execution_readiness']='completed_explicit_context_variant';value.pop('missing_inputs',None)
   value['rationale']='One-lane applicability-negative straight-travel construction; explicitly differs from the base cell maneuver and its two-/three-lane counterparts.'
   value['deliberate_differences']=['same_direction_lane_count','commanded_turn_path'];value['variable_assignments']['commanded_turn_path']['value']={'frame':'Local Cartesian: x along travel, y left, z up; meters.','initial_pose':{'x_m':20,'y_m':1.75,'heading_rad':0},'path':'Follow y=1.75 from x=20 to x=400; no lane change.','provenance':'Actual explicit configuration override; original consumed path request remains separately preserved.','signal_schedule':deepcopy(value['variable_assignments']['commanded_turn_path']['value']['signal_schedule'])}
   destination=attempt/'realized_case_definition.json';atomic(destination,value);case['definition_file']=str(destination)
 atomic(output/'delivery_index.json',index)

def document_controller_revisions(output):
 index=json.loads((output/'delivery_index.json').read_text())
 for entry in index['cells']:
  for case in entry['cases']:
   if case['status']!='validated' or not case.get('execution'):continue
   attempt=Path(case['execution']);config_path=attempt/'config.json';config=json.loads(config_path.read_text())
   if not config.get('controller_revision'):continue
   source=output.parent/case.get('definition_run_id',entry.get('run_id',index['run_id']))/'cells'/entry['cell_id']/'motor_vehicle_driver/cases.json'
   value=deepcopy(next(c for c in json.loads(source.read_text())['cases'] if c['case_id']==case['case_id']))
   value['source_definition']={'path':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'original_consumed_request_preserved':True}
   value['engineering_differences']={'controller_revision':config['controller_revision'],'gains':{k:config['controller'][k] for k in ('kp','ki')},'target_and_tolerance_unchanged':True,'identical_controller_across_delivered_triple':False,'configuration':str(config_path),'configuration_sha256':hashlib.sha256(config_path.read_bytes()).hexdigest()}
   destination=attempt/'realized_case_definition.json';atomic(destination,value);case['definition_file']=str(destination)
 atomic(output/'delivery_index.json',index)
