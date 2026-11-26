"""Build source-shaped controlled-access diagnostics for saved analysis and Core."""
import hashlib
import json
from pathlib import Path
from package_spec import AID
from access_probe import measure
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
MANIFEST=HERE/'execution-manifest.selected-draft.json'
EXAMPLE=ROOT/'runtime/fixtures/example.json'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def put(path,value,compact=False):
 path.parent.mkdir(exist_ok=True)
 path.write_text(json.dumps(value,ensure_ascii=False,**({'separators':(',',':')} if compact else {'indent':2}))+'\n')
 if path.stat().st_size>2*1024*1024:raise ValueError('diagnostic exceeds 2 MiB')
def build():
 plan=json.loads((HERE/'case-plan.json').read_text());manifest=json.loads(MANIFEST.read_text());base=json.loads(EXAMPLE.read_text())
 mapping=[json.loads(line) for line in base['files']['video_frames.jsonl'].splitlines()]
 base_trace=[json.loads(line) for line in base['files']['trace.jsonl'].splitlines()]
 for entry,case in zip(manifest['cases'],plan['cases']):
  suffix=case['case_id'].removeprefix(AID+'__');fixture=json.loads(json.dumps(base))
  for video in fixture['videos']:
   if video['path']=='reference_corner.mkv':video['path']='reference_corner.mkv'
  direction=case['requested_direction'];indicated=case['requested_indicated'];visible=case['requested_notice_visible'];y=0 if indicated else 10
  points=[{'point_id':'entry','direction':'entry','y_min_m':-1,'y_max_m':1,'device_id':'official-entry','device_source':'synthetic-entry-device','erected':True,'notice_visible':visible if direction=='entry' else True},{'point_id':'exit','direction':'exit','y_min_m':-1,'y_max_m':1,'device_id':'official-exit','device_source':'synthetic-exit-device','erected':True,'notice_visible':visible if direction=='exit' else True}]
  site={'authority_source':'synthetic-authority','highway_source':'synthetic-highway','boundary_source':'synthetic-boundary','controlled_access_determination':True,'boundary_x_m':0,'indicated_points':points,'official_notice_source':'synthetic-official-devices','vehicle_id':'driver'}
  trace=[];rows=[];frames=[]
  for i,mapped in enumerate(mapping):
   x=(-10+20*i/(len(mapping)-1)) if direction=='entry' else (10-20*i/(len(mapping)-1))
   motion=dict(base_trace[i])
   trace.append(motion)
   row={'frame':i,'native_frame':mapped['carla_frame'],'original_frame':mapped['carla_frame'],'time_s':mapped['time_s'],'actor_ids':['synthetic-vehicle'],'driver_id':'driver','lane_id':-1,'road_id':1 if x<0 else 2,'junction_id':None,'maneuver':direction,'source_ref':'synthetic-site','position_xyz_m':motion['position_m'],'boundary_xy':[x,y],'heading_deg':motion['heading_deg'],'speed_mps':motion['speed_mps'],'control':{'throttle':.2,'brake':0,'steer':.1}}
   rows.append(row);frames.append({'original_frame':row['original_frame'],'time_s':row['time_s'],'vehicle_id':'driver','xy':[x,y],'source_ref':'synthetic-site'})
  history={'source_kind':'synthetic_diagnostic_fixture','assignment_id':AID,'case_id':case['case_id'],'reviewed_site_sha256':'a'*64,'map_sha256':'b'*64,'driver_actor_id':'driver','ego_actor_id':'synthetic-vehicle','actor_ids':['synthetic-vehicle'],'authority_source':site['authority_source'],'highway_source':site['highway_source'],'boundary_source':site['boundary_source'],'official_notice_source':site['official_notice_source'],'public_highway':True,'controlled_access_determination':True,'authority_designated_devices':True,'boundary_x_m':0,'indicated_points':points,'target_point':{'direction':direction,'indicated':indicated,'notice_visible':visible,'point_id':direction if indicated else 'none','crossing_y_m':y,'source_ref':'synthetic-target'},'requested_direction':direction,'samples':rows}
  history_text=json.dumps(history,sort_keys=True)+'\n';measurement_text=json.dumps(measure(site,frames),sort_keys=True)+'\n'
  trace_text=base['files']['trace.jsonl']
  frame_rows=[{**mapped,'video_frame':i,'native_frame':mapped['carla_frame']} for i,mapped in enumerate(mapping)]
  frame_text=''.join(json.dumps(row,sort_keys=True)+'\n' for row in frame_rows)
  receipt={'source_kind':'synthetic_diagnostic_fixture','diagnostic_fixture':True,'case_id':case['case_id'],'history_sha256':hashlib.sha256(history_text.encode()).hexdigest(),'trace_sha256':hashlib.sha256(trace_text.encode()).hexdigest(),'frame_map_sha256':hashlib.sha256(frame_text.encode()).hexdigest(),'measurement_sha256':hashlib.sha256(measurement_text.encode()).hexdigest(),'physical_acceptance':False,'legal_verdict':None}
  fixture['files'].update({'access-history.json':history_text,'access-measurement.json':measurement_text,'trace.jsonl':trace_text,'video_frames.jsonl':frame_text,'original-source-receipt.json':json.dumps(receipt,sort_keys=True)+'\n'})
  generator=HERE/'diagnostics'/(suffix+'-generator.json');put(generator,fixture,compact=True)
  recipe=HERE/'diagnostics'/(suffix+'-recipe.json');put(recipe,{'format':'worker-fixture-recipe','sources':[{'path':'diagnostic-input.json','source':'runtime/fixtures/example.json','sha256':sha(EXAMPLE)}],'generator':{'source':str(generator.relative_to(ROOT)),'sha256':sha(generator)}})
  keys=('controlled_access_authority','official_erected_devices','vehicle_boundary_crossing')
  reqs=[{'disposition_index':d['disposition_index'],'requirement':d['requirement'],'source':d['source'],'output_key':keys[d['disposition_index']],'method':'source_sealed_access_measurement','value_type':'object','kind':'measured','inputs':['access-history.json','original-source-receipt.json','trace.jsonl']} for d in plan['requirement_dispositions']]
  contract=HERE/'diagnostics'/(suffix+'-measurement-contract.json');put(contract,{'format':'worker-measurement-contract','case_id':case['case_id'],'requirements':reqs,'negative':{'remove':['access-history.json'],'error_contains':'Missing required source: access-history.json'}})
  entry['fixture_recipe']=str(recipe.relative_to(ROOT));entry['measurement_contract']=str(contract.relative_to(HERE));entry['measurement_procedure']={'entrypoint':'analysis.py','method':'source-sealed Native boundary crossing and independently sourced official device readback'}
 put(MANIFEST,manifest);return len(manifest['cases'])
if __name__=='__main__':print('controlled-access compatibility inputs:',build())
