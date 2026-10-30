"""Project explicitly declared synthetic facts through existing Core assumptions."""
import hashlib,json,os
from pathlib import Path
from batch_pipeline.store import atomic


def assumptions(context):
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
 from expected_labels import first_scene,sha,load
 from traffic_spec_adapter.validate import validate_output
 values=assumptions(context);root=attempt/'traffic_spec';path=root/'trace.json'
 if not values:return
 if first_scene(path).get('assumptions')==values:return
 if first_scene(path).get('assumptions'):raise ValueError('Existing assumptions must not be overwritten')
 token='"links":[]';replacement=token+',"assumptions":'+json.dumps(values,separators=(',',':'))
 temporary=root/'trace.context-pending.json';count=0;before=sha(path)
 with path.open() as source,temporary.open('w') as target:
  remainder=''
  while True:
   chunk=source.read(1024*1024)
   if not chunk:break
   text=remainder+chunk
   # Split outside a partial replacement token.
   cut=max(0,len(text)-64);candidate=text.rfind(token,max(0,cut-len(token)),min(len(text),cut+len(token)))
   if candidate>=0 and candidate<cut<candidate+len(token):cut=candidate
   piece,remainder=text[:cut],text[cut:];count+=piece.count(token);target.write(piece.replace(token,replacement))
  count+=remainder.count(token);target.write(remainder.replace(token,replacement))
 expected=load(root/'adapter_report.json')['frames']
 if count!=expected:temporary.unlink();raise ValueError('Assumption projection frame count mismatch: %s/%s'%(count,expected))
 archive=root/'trace.before-expected-context.json'
 if archive.exists():temporary.unlink();raise ValueError('Context projection archive already exists')
 os.replace(path,archive);os.replace(temporary,path)
 try:validate_output(root,validator)
 except Exception:
  os.replace(path,temporary);os.replace(archive,path);raise
 atomic(root/'authored_context_projection.json',{'source_trace':str(archive),'source_sha256':before,'trace_sha256':sha(path),'frames':count,'assumptions':values,'provenance':context,'projection':'Only scene assumptions added; original users, structures, devices, times and observations preserved byte-for-byte'})
 atomic(attempt/'capture/authored_test_context.json',{'assumptions':values,'provenance':context,'native_graphs_unchanged':True})
