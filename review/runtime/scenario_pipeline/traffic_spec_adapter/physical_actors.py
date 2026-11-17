"""Opt-in genuine physical animal registry; source identity is not legal status."""
import hashlib,json,math
from pathlib import Path

def digest(path):
 return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load_registry(path):
 path=Path(path);value=json.loads(path.read_text());assert value['version']==1;assert value['actors'];seen=set()
 for record in value['actors']:
  ident=record['actor_id'];assert type(ident) is int and ident>0 and ident not in seen;seen.add(ident)
  assert record['physical_class']=='animal' and record['engine_type']=='static.prop.mesh'
  assert record['body_forward_local_axis']=='+Y' and record['body_heading_offset_degrees']==90;attrs=record['blueprint_attributes'];assert attrs['mesh_path']=='/Game/AnimaSim/Static/Dynamic/Cow/SM_Cow.SM_Cow';assert float(attrs['mass'])==400 and float(attrs['scale'])==1
  assets=record['source_asset_files'];assert assets and any(x['path'].endswith('/Cow/SM_Cow.uasset') for x in assets) and any(x['path'].endswith('/Cow/SM_Cow.uexp') for x in assets)
  for source in assets:assert Path(source['path']).is_file() and digest(source['path'])==source['sha256'],'Animal asset identity/hash mismatch'
  proof=record['capability_proof'];assert set(proof)=={'native_outcome','pixel_body_audit','closure','derivation'}
  for source in proof.values():assert digest(source['path'])==source['sha256'],'Animal physical proof identity/hash mismatch'
  outcome=json.loads(Path(proof['native_outcome']['path']).read_text());pixels=json.loads(Path(proof['pixel_body_audit']['path']).read_text());closure=json.loads(Path(proof['closure']['path']).read_text());assert outcome.get('grounded') is True and outcome['native_minimum_body_vertex_height_min_max_m'][0]>=-.05 and outcome['native_minimum_body_vertex_height_min_max_m'][1]<=.1;assert outcome['passed'] and outcome['actual_displacement_m']>10 and pixels['passed'] and closure['restored'] and closure['original_parent_wait']['process_wait_completed'];assert pixels['source_probe']==str(Path(proof['native_outcome']['path']).parent)
 return {'sha256':digest(path),'path':str(path.resolve()),'value':value,'actors':{x['actor_id']:x for x in value['actors']}}

def classify_record(record,registry):
 expected=registry['actors'].get(record['actor_id'])
 if expected is None:
  assert 'physical_classification' not in record,'Unregistered physical classification';return None
 assert record['blueprint']==expected['engine_type']
 for name,value in expected['blueprint_attributes'].items():assert record['blueprint_attributes'].get(name)==value,'Native animal attributes differ from bound registry'
 return {'registry_sha256':registry['sha256'],'actor_id':record['actor_id'],'physical_class':'animal','mesh_path':expected['blueprint_attributes']['mesh_path'],'body_heading_offset_degrees':90,'body_forward_local_axis':'+Y'}

def observe_actor(actor,registry,actor_state):
 state=actor_state(actor);classification=classify_record(state,registry);assert classification is not None;state['physical_classification']=classification;state['native_actor_heading_deg']=state['heading_deg'];state['heading_deg']=(state['heading_deg']+90)%360;h=math.radians(state['heading_deg']);state['accel_longitudinal_mps2']=state['acceleration_mps2'][0]*math.cos(h)+state['acceleration_mps2'][1]*math.sin(h);return state

def validate_frame(records,registry):
 seen=set()
 for record in records:
  ident=record['actor_id'];assert ident not in seen;seen.add(ident);classification=classify_record(record,registry)
  if classification is not None:assert record.get('physical_classification')==classification,'Frame lost/corrupted registered physical actor identity'
 assert set(registry['actors'])<=seen,'Original frame missing mandatory registered animal'
