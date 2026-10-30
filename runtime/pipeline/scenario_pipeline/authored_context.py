"""Project explicitly declared synthetic facts through existing Core assumptions."""
import hashlib,json,os
from pathlib import Path
from batch_pipeline.store import atomic


def assumptions(context):
 from intentions import validate_context
 validate_context(context)
 result=[]
 district=context.get('district')
 if district:
  result.extend([['asm.business_district',district=='business_or_residential'],['asm.residential_district',False],['asm.other_area',district=='other_area']])
 if context.get('stopping_reference'):result.append(['asm.no_crosswalk_on_approach',True])
 if context.get('fixed_non_swept_conditions') and (context.get('maneuver') == 'lane_change' or not context.get('core_assumptions')):
  result.extend([['asm.driver_ascertained_lane_change_safe',True],['asm.appropriate_signal_fixed',True],['asm.clearly_marked_lanes',True]])
 for pair in context.get('core_assumptions', []):
  if not isinstance(pair,list) or len(pair)!=2 or not isinstance(pair[0],str) or not pair[0] or not isinstance(pair[1],bool):raise ValueError('Explicit Core assumptions require [name, boolean]')
  result.append(pair)
 if len({pair[0] for pair in result})!=len(result):raise ValueError('Duplicate Core assumption identity')
 return result


def inject(attempt,context,validator):
 """Project explicit context per frame; keep scene facts and intent separate."""
 from expected_labels import sha,load
 from traffic_spec_adapter.validate import validate_output
 from intentions import project,validate_scene_intents
 from trace_json import scenes,replace_field
 values=assumptions(context);root=attempt/'traffic_spec';path=root/'trace.json'
 if not values and not context.get('intent_declarations'):return
 temporary=root/'trace.context-pending.json';before=sha(path);count=0;changed=False
 mapping_path=attempt/'video_frames.jsonl';mapping=[]
 if mapping_path.exists():
  with mapping_path.open() as f:mapping=[json.loads(line) for line in f if line.strip()]
 try:
  with temporary.open('x') as output:
   output.write('{"scenes":[')
   for scene,raw in scenes(path):
    if values:
     existing=scene.get('assumptions',[])
     if existing and existing!=values:raise ValueError('Existing assumptions must not be overwritten')
     if existing!=values:raw=replace_field(raw,'assumptions',values);scene['assumptions']=values;changed=True
    row=mapping[count] if count<len(mapping) else {}
    if row and abs(row.get('time_s',scene['t']/1000)-scene['t']/1000)>.001:
     raise ValueError('Intent original-frame/time join mismatch')
    if context.get('intent_declarations'):
     records=project(context,scene,original_frame=row.get('original_frame',row.get('carla_frame',row.get('frame'))),time_s=row.get('time_s',scene['t']/1000))
     if scene.get('intents',[]) and scene['intents']!=records:raise ValueError('Existing intents must not be overwritten')
     if scene.get('intents',[])!=records:raw=replace_field(raw,'intents',records);scene['intents']=records;changed=True
    validate_scene_intents(scene)
    if count:output.write(',')
    output.write(raw);count+=1
   output.write(']}\n')
  expected=load(root/'adapter_report.json')['frames']
  if count!=expected:raise ValueError('Context projection frame count mismatch')
  if not changed:temporary.unlink();return
  archive=root/'trace.before-expected-context.json'
  if archive.exists():raise ValueError('Context projection archive already exists')
  os.replace(path,archive);os.replace(temporary,path)
  try:validate_output(root,validator)
  except Exception:
   os.replace(path,temporary);os.replace(archive,path);raise
  atomic(root/'authored_context_projection.json',{'source_trace':str(archive),'source_sha256':before,'trace_sha256':sha(path),'frames':count,'assumptions':values,'provenance':context,'projection':'Only explicit context and per-frame intentions; all other scene tokens preserved'})
  atomic(attempt/'capture/authored_test_context.json',{'assumptions':values,'provenance':context,'native_graphs_unchanged':True})
 except Exception:
  # Retain failed staged evidence for diagnosis; never overwrite the original.
  raise
