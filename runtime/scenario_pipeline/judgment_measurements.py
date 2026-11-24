"""Atom-only judgment measurements from the delivered trace; no legal verdicts."""
import copy
import json
from pathlib import Path
from collections import defaultdict
from trace_json import scenes
from judgment_measurement_specs import derive_specs
from judgment_atoms import ATOMS, UNITS, Sources, actors, contract, ref, sha, value, regions

VERSION='ontology-atom-measurements-v2'

def _definition(folder,metadata):
 hashes={r.get('definition_sha256')for r in metadata.get('label_record',{}).get('legal_judgment',{}).get('references',[])if isinstance(r,dict)}-{None}
 for name in('evidence/accepted_case_definition.json','evidence/expected_label_case_definition.json','evidence/case.json','case.json','definition.json'):
  p=folder/name
  if p.is_file()and sha(p)in hashes:return json.loads(p.read_text()),{'path':name,'sha256':sha(p)}
 definition=metadata.get('acceptance',{}).get('definition')
 if isinstance(definition,dict):
  import hashlib
  digest=hashlib.sha256(json.dumps(definition,sort_keys=True).encode()).hexdigest()
  if digest in hashes:return definition,{'metadata_path':'acceptance.definition','sha256':digest}
 return None,None

def _selection(definition,metadata):
 selected=derive_specs(definition,metadata)
 channels=definition.get('recording_description',{}).get('channels',[])
 for request in selected['specs']:
  if request['quantity']not in ATOMS:raise ValueError('Quantity must be a current ontology atom')
  statements=[c['uncertainty']for c in channels if isinstance(c,dict)and c.get('name')in request['source_variables']and c.get('uncertainty')]
  if statements:request['source_uncertainty']=list(dict.fromkeys(request.get('source_uncertainty',[])+statements))
 return selected

def _measurement_context(folder):
 p=folder/'manifest.json';manifest=json.loads(p.read_text())if p.is_file()else{}
 provenance=manifest.get('measurement_provenance',{});projection={};used=[]
 sight=provenance.get('st.sight_distance',{})
 for key in('new1000_projection','new_projection','projection'):
  source=sight.get(key)
  if not isinstance(source,dict)or not source.get('path'):continue
  path=Path(source['path']);path=path if path.is_absolute()else folder/path
  if not path.is_file()or sha(path)!=source.get('sha256'):continue
  data=json.loads(path.read_text());reference=ref(path)
  try:reference['path']=str(path.relative_to(folder))
  except ValueError:pass
  used.append(reference)
  projection={r['trace_t']:r for r in data.get('scenes',[])if'trace_t'in r};break
 return provenance,projection,used

def _uncertainty(request,scene,context,provenance,projection,reading):
 error={'kind':'unknown'};out={'error':error};q=request['quantity']
 if request.get('source_uncertainty'):error['source_statements']=request['source_uncertainty']
 declared=provenance.get(q,{})
 if isinstance(declared.get('error'),dict):error.update(copy.deepcopy(declared['error']))
 supplement=context.get('supplement',{})
 if q=='env.visibility':
  source=supplement.get('environmental_mapping',{})
  if source.get('visibility_kind')=='sampled_lower_bound':out['bound']='at_least'
  if source.get('visibility_uncertainty'):error['description']=source['visibility_uncertainty']
 if q=='st.sight_distance':
  raw=context.get('capture',{}).get('visibility')or{};mapping=supplement.get('visibility_mapping',{})
  recovered=projection.get(scene['t'])
  if recovered:
   raw=recovered.get('measurement',{}).get('visibility',raw);mapping=recovered.get('mapping',mapping)
  horizons=[a.get('any_body_sight_horizon',{})for a in raw.get('approaches',[])]
  if mapping.get('value_m')==reading and mapping.get('lower_bound_m')==reading or horizons and all(h.get('bound')in('at_least','first_sampled_occlusion')for h in horizons):out['bound']='at_least'
  sampling={k:mapping[k]for k in('scan_step_m','horizon_tolerance_m','lower_bound_m','upper_bound_m','search_censored','measurement_method','visibility_criterion')if k in mapping}
  sampling.update({k:raw[k]for k in('scan_step_m','horizon_tolerance_m','maximum_search_distance_m','visibility_criterion','distance_convention')if k in raw})
  if horizons:sampling['approach_horizons']=[{k:h[k]for k in('bound','distance_m','bracket_m')if k in h}for h in horizons]
  if sampling:error['sampling']=sampling
  if mapping.get('search_censored')is True and'bound'not in out:raise ValueError('Censored sight result lacks verified bound')
 return out

def _source_windows(folder,times,frames):
 """Preserve explicit producer-defined events, including sampled brackets."""
 collected={};bindings=[];unresolved=[]
 def record(label,bracket,source):
  if not(isinstance(bracket,list)and len(bracket)==2 and all(type(x)in(int,float)for x in bracket)):return
  covered=[i for i,t in enumerate(times)if round(bracket[0]*1000)<=t<=round(bracket[1]*1000)]
  if not covered:return
  key=(label,bracket[0],bracket[1])
  collected[key]={'start_scene':covered[0],'end_scene':covered[-1],'source_time_window_s':bracket,'source_event':source}
 def visit(node,label):
  if isinstance(node,dict):
   if isinstance(node.get('sample_window_s'),list):record(label,node['sample_window_s'],{k:node[k]for k in('method','onset_time_bracket_s','departure_time_bracket_s','sampling_distance_interval_m')if k in node})
   if node.get('status')=='observed'and isinstance(node.get('bracket_s'),list):record(label,node['bracket_s'],{k:node[k]for k in('method','reference','footprint_reference','uncertainty_s','geometry_uncertainty_m','bracket_frames')if k in node})
   for key,v in node.items():visit(v,label+'.'+key)
  elif isinstance(node,list):
   for index,v in enumerate(node):visit(v,label+'.'+str(index))
 for name in('observed_stopping_event.json','ego_signal_lead_distance.jsonl','entry_event_evidence.jsonl'):
  p=folder/'evidence'/name
  if not p.is_file():continue
  bindings.append({'path':str(p.relative_to(folder)),'sha256':sha(p)})
  if p.suffix=='.jsonl':
   with p.open()as stream:
    for line in stream:visit(json.loads(line),p.stem)
  else:
   event=json.loads(p.read_text());visit(event,p.stem)
   if name=='observed_stopping_event.json':
    start,end=event.get('first_applied_control_frame'),event.get('cessation_frame')
    if type(start)is int and type(end)is int and start-1 in frames and end in frames:
     first,last=frames.index(start-1),frames.index(end)
     record(p.stem,[times[first]/1000,times[last]/1000],{'method':'original pre-control frame through source-engineering cessation frame','first_applied_control_frame':start,'cessation_frame':end,'uncertainty':event.get('uncertainty'),'not_a_legal_stop_threshold':True})
    else:unresolved.append({'authored_observable':'observed_stopping_event','reason':'source_event_frame_window_not_in_delivered_trace'})
 windows={};counts=defaultdict(int)
 for (label,low,high),data in sorted(collected.items(),key=lambda item:(item[0][1],item[0][2],item[0][0])):
  counts[label]+=1;windows[label+'@'+str(counts[label])]=data
 return windows,bindings,unresolved

def _merge_observation(previous,current):
 if {k:v for k,v in previous.items()if k!='error'}!={k:v for k,v in current.items()if k!='error'}:raise ValueError('Conflicting atom values at synchronized instant')
 a,b=previous['error'],current['error']
 if {k:v for k,v in a.items()if k!='source_statements'}!={k:v for k,v in b.items()if k!='source_statements'}:raise ValueError('Conflicting uncertainty methods at synchronized instant')
 statements=list(dict.fromkeys(a.get('source_statements',[])+b.get('source_statements',[])))
 if statements:a['source_statements']=statements

def _extract(folder,metadata,trace_path):
 definition,binding=_definition(folder,metadata)
 selected=_selection(definition,metadata)if definition is not None else{'specs':[],'unresolved':[{'reason':'authored_definition_hash_binding_not_found'}]}
 phrases={r.get('phrase')for r in metadata.get('label_record',{}).get('legal_judgment',{}).get('references',[])if isinstance(r,dict)}
 for request in selected['specs']:
  if request['phrase']not in phrases:raise ValueError('Measurement phrase is not an unchanged legal reference')
 context=Sources(folder);provenance,projection,projection_refs=_measurement_context(folder)
 groups=defaultdict(list);gaps={};times=[];frames=[]
 def gap(request,reason):
  key=json.dumps([request,reason],sort_keys=True)
  if key not in gaps:gaps[key]={'quantity':request['quantity'],'actor_role':request['actor_role'],'phrase':request['phrase'],'reason':reason,'scene_count':0,'source_variables':request['source_variables'],'authored_paths':request['authored_paths']}
  gaps[key]['scene_count']+=1
 try:
  for index,(scene,_)in enumerate(scenes(trace_path)):
   times.append(scene['t']);observations=context.frame(scene);users=observations['users'];frames.append(observations['capture'].get('original_frame',observations['motion'].get('frame')))
   for request in selected['specs']:
    try:ids=actors(observations,request['actor_role'])
    except ValueError as exc:gap(request,str(exc));continue
    for ident in ids:
     user=users[ident];q=request['quantity'];targets=[None];others=[None]
     if q.startswith('st.')and q not in('st.grade','st.curvature')or q=='rel.occupies':
      try:targets=regions(scene,user,request)
      except ValueError as exc:gap(request,str(exc));continue
      if not targets:
       if not request.get('optional_region_kind'):gap(request,'source_bound_region_unavailable')
       continue
     if request.get('other_role'):
      try:others=[users[i]for i in actors(observations,request['other_role'])]
      except ValueError as exc:gap(request,str(exc));continue
     for region in targets:
      for other in others:
       if other is not None and other['track']==ident:gap(request,'relation_requires_distinct_actors');continue
       reading=value(scene,user,request,observations,region,other)
       if reading is None:gap(request,'supported_trace_atom_value_unavailable');continue
       entry={'quantity':q,'road_user':'subject'if ident==scene['subject']else ident,'value':reading,'unit':UNITS[q],**_uncertainty(request,scene,observations,provenance,projection,reading),'statistic':'instant','window':'recording@scene-'+str(index),'phrase':request['phrase'],'source':'trace'}
       if region is not None:entry['region']=region['id']
       if other is not None:entry['other_road_user']='subject'if other['track']==scene['subject']else other['track']
       if request.get('component'):entry['component']=request['component']
       key=json.dumps({k:entry[k]for k in('quantity','road_user','phrase','region','other_road_user','component')if k in entry},sort_keys=True)
       if groups[key]and groups[key][-1]['window']==entry['window']:
        _merge_observation(groups[key][-1],entry)
       else:groups[key].append(entry)
  context.finish()
 finally:context.close()
 if not times:raise ValueError('Cannot measure empty trace')
 entries=[]
 for rows in groups.values():
  comparable=lambda row:{k:v for k,v in row.items()if k not in('window','statistic')}
  if len(rows)==len(times)and all(comparable(r)==comparable(rows[0])for r in rows[1:]):
   entries.append(dict(rows[0],statistic='constant',window='recording'))
  else:entries.extend(rows)
 windows={'recording':{'start_scene':0,'end_scene':len(times)-1}}
 windows.update({'recording@scene-'+str(i):{'scene_index':i,'trace_t':t}for i,t in enumerate(times)})
 event_windows,event_sources,event_gaps=_source_windows(folder,times,frames);windows.update(event_windows)
 for entry in entries:
  index=windows[entry['window']].get('scene_index')
  occurrences=[name for name,window in event_windows.items()if index is None or window['start_scene']<=index<=window['end_scene']]
  if occurrences:entry['occurrence_windows']=occurrences
 unresolved=selected['unresolved']+list(gaps.values())+event_gaps
 result={'judgment_measurements':entries,'judgment_measurement_windows':windows,'judgment_measurement_unresolved':unresolved}
 measurement_provenance={'method':VERSION,'selection':'authored_scenario_variables_and_recording_description','definition':binding,'trace_sha256':sha(trace_path),'trace_time_unit':'ms','trace_time_source':'kin.time: delivered scene.t','ontology':contract(),'extractor_sha256':sha(Path(__file__)),'atom_reader_sha256':sha(Path(__file__).with_name('judgment_atoms.py')),'mapping_sha256':sha(Path(__file__).with_name('judgment_measurement_specs.py')),'selected_quantities':selected['specs'],'source_channels':selected.get('source_channels',[]),'authored_context':selected.get('authored_context',[]),'intentionally_varied':selected.get('intentionally_varied',[]),'controller_settings':selected.get('controller_settings',[]),'actor_identity_sources':context.sources,'uncertainty_sources':projection_refs,'source_events':event_sources,'complete':not unresolved,'uncertainty':'Unknown unless established source uncertainty is supplied; source/method never changes quantity identity.'}
 return result,measurement_provenance

def enrich_judgment_metadata(folder,metadata,*,trace_path=None):
 if metadata.get('expected_label')!='judgment call':return metadata
 folder=Path(folder);trace_path=Path(trace_path)if trace_path is not None else folder/'trace.json'
 fields,provenance=_extract(folder,metadata,trace_path);result=copy.deepcopy(metadata);result.update(fields)
 result.setdefault('provenance',{})['judgment_measurements']=provenance
 return result

def validate_judgment_metadata(metadata,trace_path):
 if metadata.get('expected_label')!='judgment call':
  if metadata.get('judgment_measurements'):raise ValueError('Judgment measurements require unchanged judgment-call label')
  return
 if'judgment_measurements'not in metadata:raise ValueError('Atom-only judgment metadata is required')
 provenance=metadata.get('provenance',{}).get('judgment_measurements',{})
 if provenance.get('method')!=VERSION:raise ValueError('Only the current atom-only metadata contract is supported')
 for entry in metadata['judgment_measurements']:
  if entry.get('quantity')not in ATOMS:raise ValueError('Quantity is not an ontology atom ID')
  if entry.get('source')!='trace':raise ValueError('Atom reading must identify its delivered-trace source')
  if entry.get('unit')!=UNITS.get(entry['quantity']):raise ValueError('Atom unit differs from contract')
  if entry.get('statistic')not in('instant','constant'):raise ValueError('Unsupported atom measurement statistic')
  if entry.get('error',{}).get('kind')not in('unknown','bound'):raise ValueError('Explicit uncertainty is required')
 fields,expected=_extract(Path(trace_path).parent,metadata,Path(trace_path))
 # Producer fingerprints describe how a delivery was created. They are not
 # measurements and do not invalidate unchanged readings after a code edit.
 fingerprints={'extractor_sha256','atom_reader_sha256','mapping_sha256'}
 provenance={k:v for k,v in provenance.items()if k not in fingerprints}
 expected={k:v for k,v in expected.items()if k not in fingerprints}
 if any(metadata.get(k)!=v for k,v in fields.items())or provenance!=expected:raise ValueError('Atom metadata differs from authored selection or delivered values/windows/provenance')
