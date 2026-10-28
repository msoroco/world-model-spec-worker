"""Build four partition-04 exact packages from this checkout's frozen inputs."""
import hashlib, importlib.util, json, shutil, xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
RUNTIME=REPO/'runtime/main-pipeline-v1'
PILOT=REPO/'work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver'
SOURCE=REPO/'work/testing__C109705__NRS-484B-400-2b__motor_vehicle_driver/build_partition.py'
PARTITION=[a for a in json.loads((REPO/'partitions/demo-test-04.json').read_text())['assignment_ids'] if 'C10301__' not in a]
spec=importlib.util.spec_from_file_location('p01_current_scenes',SOURCE);p01=importlib.util.module_from_spec(spec);spec.loader.exec_module(p01)
MODES={
 'NRS-484B-127-1':('winter_follow', [('wet_gap_15',{'weather_surface':('wet','label'),'commanded_gap_m':(15.,'m')}),('ice_gap_30',{'weather_surface':('ice_or_snow','label'),'commanded_gap_m':(30.,'m')})]),
 'NRS-484B-600-1c':('signed_speed',[('below_sign',{'target_speed_mps':(12.,'m/s')}),('above_sign',{'target_speed_mps':(16.,'m/s')})]),
 'NRS-484B-307-6a':('signal_amber',[('brake_before',{'stop_duration_s':(1.,'s')}),('continue_through',{'stop_duration_s':(0.,'s')})]),
 'NRS-484B-250-4':('signal_dark',[('full_stop',{'stop_duration_s':(1.,'s')}),('no_stop',{'stop_duration_s':(0.,'s')})])}
METHODS={
 'drv.following':'same-frame subject/leader pose, heading and full-body gap history',
 'drv.time_gap':'original body gap divided by observed relative motion, with censoring at zero closure',
 'rel.surface_gap':'same-frame nearest original body separation',
 'rel.ahead_behind_in_lane':'native lane projection and same-direction actor order',
 'kin.speed':'original native actor speed at 20 Hz',
 'env.wet_road':'commanded weather plus original camera and native map surface evidence; physical wetness unverified',
 'env.ice_or_snow':'ice/snow capability explicitly absent from pinned Core and native fixture; retained unknown',
 'drv.queue_behind':'same-frame ordered actor and lane inventory',
 'drv.hard_deceleration':'original speed derivative with time sampling and controller brake input',
 'dev.speed_limit_sign':'authored OpenDRIVE sign and native landmark/render inventory',
 'dev.governs':'sign road ID, lane validity and subject native lane path',
 'drv.within_signed_zone':'original actor footprint across sign longitudinal zone',
 'rel.occupies':'original full body relative to signed road lane polygon',
 'dev.position':'native landmark s/t and original actor distance',
 'dev.traffic_signal':'authored signal, native signal actor state and original camera view',
 'dev.inoperative':'native signal state/renderer probe; inoperative physical condition remains unverified',
 'st.lane_enters':'native incoming road links and original lane projection',
 'kin.time':'original source timestamp and CARLA frame',
 'drv.entering_intersection':'original body/junction boundary entry time',
 'st.intersection':'native junction polygon and original full body',
 'drv.crossing_line':'original body front crossing native stop-line/crosswalk geometry',
 'drv.stopping_distance':'original speed and available distance to line, with brake response',
 'st.stop_line':'native stop-line inventory and original camera view',
 'st.crosswalk':'native crosswalk vertices and original camera view',
 'st.sight_distance':'original ray/obstruction probe and approach geometry; physical visibility unknown',
 'rel.visible':'same-frame other actor and obstruction/renderer evidence; visual fact unknown',
 'drv.stopped':'original stationary interval before crossing',
 'drv.arrival_order':'original ego/opposing entry-time brackets',
 'drv.in_intersection':'original full body inside native junction boundary',
 'drv.yields_to':'original stop interval and opposing passage order'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def scene(folder,mode):
 path=folder/'scene.xodr'
 if mode in ('winter_follow','signed_speed'):
  p01.straight_scene(path)
  if mode=='signed_speed':
   root=ET.parse(path).getroot();road=root.find('road[@id="1"]');signals=ET.SubElement(road,'signals')
   ET.SubElement(signals,'signal',{'id':'10','name':'speed_limit_45_kmh','s':'45','t':'-5','zOffset':'0','hOffset':'0','roll':'0','pitch':'0','orientation':'+','dynamic':'no','country':'OpenDRIVE','type':'274','subtype':'0','value':'45','unit':'km/h','height':'2.1','width':'.7'})
   path.write_text(ET.tostring(root,encoding='unicode')+'\n')
 else:
  root=ET.parse(PILOT/'intersection.xodr').getroot();road=root.find('road[@id="1"]');signals=ET.SubElement(road,'signals')
  ET.SubElement(signals,'signal',{'id':'20','name':'intersection_traffic_signal','s':'62','t':'-5','zOffset':'0','hOffset':'0','roll':'0','pitch':'0','orientation':'+','dynamic':'yes','country':'OpenDRIVE','type':'1000001','subtype':'0','value':'0','height':'2.4','width':'.6'})
  objects=ET.SubElement(road,'objects')
  ET.SubElement(objects,'object',{'id':'21','name':'near_side_crosswalk','type':'crosswalk','s':'68','t':'0','zOffset':'0','hdg':'0','length':'3','width':'14','height':'.01'})
  path.write_text(ET.tostring(root,encoding='unicode')+'\n')
def fixture(folder,mode):
 source=REPO/'work/_shared/fixtures/base-v3';target=folder/'fixture-diagnostic'
 if target.exists():shutil.rmtree(target)
 shutil.copytree(source,target)
 trace=[json.loads(s) for s in (target/'trace.jsonl').read_text().splitlines()]
 evidence=[json.loads(s) for s in (target/'capture/evidence.jsonl').read_text().splitlines()]
 channels=target/'channels';channels.mkdir(exist_ok=True)
 write(target/'native-controls.json',{'landmarks':[],'crosswalk_vertices_m':[],'traffic_light_actors':[],
   'native_object_names':[],'actor_inventory':[],'scope':'retained straight-road diagnostic; no assigned signal/sign/weather acquired'})
 values={'kin.position':[],'kin.heading':[],'kin.speed':[],'source_observations':[]}
 for point,event in zip(trace,evidence):
  if point['frame']!=event['original_frame']:raise ValueError('Fixture frame mismatch')
  values['kin.position'].append(point['position_m']);values['kin.heading'].append(point['heading_deg']);values['kin.speed'].append(point['speed_mps'])
  values['source_observations'].append({'mode':mode,'route_index':None,'ego_body_vertices_m':event['ego']['body_vertices_m'],
   'other':None,'native_light_state':None,'road_projection':event['world']['road_projection'],
   'native_observations':event['original_observations'],'native_topology_reference':None,
   'native_controls_reference':'native-controls.json','traffic_light_states':[],'weather_surface_context':None,
   'applied_control':point['control'],'scenario_motion_completed':False})
 for name,items in values.items():
  with (channels/(name+'.jsonl')).open('w') as f:
   for point,value in zip(trace,items):f.write(json.dumps({'time_s':point['time_s'],'value':value})+'\n')
 provenance=json.loads((target/'fixture-provenance.json').read_text())
 provenance['partition04_adaptation']=['Current checkout pinned retained three-frame straight-road source.',
  'Channels created before analysis from retained original trace/evidence.',
  'No assigned maneuver, sign, signal phase, weather or other actor demonstrated.',
  'Software compatibility only; no physical or statutory acceptance.']
 write(target/'fixture-provenance.json',provenance)
def build(aid):
 folder=REPO/'work'/aid;folder.mkdir(parents=True,exist_ok=True)
 inp=REPO/'inputs'/aid/'assignment.json';assignment=json.loads(inp.read_text())
 mode,settings=MODES[assignment['law_id']]
 for sub in ('tests','proposals','constructions'): (folder/sub).mkdir(exist_ok=True)
 if folder!=ROOT:
  shutil.copyfile(ROOT/'runner.py',folder/'runner.py');shutil.copyfile(ROOT/'analyze.py',folder/'analyze.py');shutil.copyfile(ROOT/'tests/test_scenario.py',folder/'tests/test_scenario.py')
 scene(folder,mode);fixture(folder,mode)
 desc={'channels':[{'name':n,'unit':unit,'sampling_rate_hz':20,'method':method,
  'time_window':'all original recorded ticks','reference_frame':'CARLA world/native OpenDRIVE',
  'uncertainty':'finite source sampling; legal/physical predicate requires native measurement'} for n,unit,method in [
  ('kin.position','structured','original world XYZ'),('kin.heading','deg','original yaw'),('kin.speed','m/s','original velocity norm'),
  ('source_observations','structured','same-frame original actors, full body, native map, control/weather inventory')]],
  'context_inputs':[],'limitations':['Three-frame straight-road diagnostic does not prove assigned phenomenon.']}
 cases=[]
 for label,assignments in settings:
  cases.append({'case_id':aid+'__'+label,'target_law_id':assignment['law_id'],'target_type':'boundary_probe',
   'rationale':'Freeze one control/context contrast and measure original source response; no legal cutoff is inferred.',
   'variable_assignments':{k:{'value':v,'unit':u,'kind':'controller' if k!='weather_surface' else 'context'} for k,(v,u) in assignments.items()},
   'unresolved_judgment_calls':[assignment['law']['text'],'public-way/device/weather authority is synthetic or unverified'],
   'recording_description':desc})
 write(folder/'proposals/cases.json',{'status':'draft','cell_id':assignment['cell_id'],'actor':assignment['actor'],'sweep_specs':[],'cases':cases})
 terms=[x['term'] for x in assignment['source_observation_terms']]
 mapping={t:{'evidence':METHODS[t],'channels':[t if t in ('kin.speed','kin.position','kin.heading') else 'source_observations'],
  'source_refs':['scene.xodr','capture/evidence.jsonl','native-controls.json']} for t in terms}
 plan={'assignment_id':aid,'actor':assignment['actor'],'cell_id':assignment['cell_id'],'law_id':assignment['law_id'],
  'cases':cases,'comparisons':[{'case_ids':[c['case_id'] for c in cases],
   'deliberate_differences':[str([c['variable_assignments'] for c in cases])],
   'fixed_conditions':['same authored road, actor blueprint, cameras and base controller']}],
  'observations':[{'name':c['name'],'mandatory':True,'description':c['method']} for c in desc['channels']],
  'source_observation_mapping':mapping,
  'sources':[{'path':str(inp.relative_to(REPO)),'sha256':sha(inp)},
   {'path':'runtime/main-pipeline-v1/SOURCE-MANIFEST.json','sha256':sha(RUNTIME/'SOURCE-MANIFEST.json')},
   {'path':'skills/worker-preparation/SKILL.md','sha256':sha(REPO/'skills/worker-preparation/SKILL.md')},
   {'path':str((folder/'scene.xodr').relative_to(REPO)),'sha256':sha(folder/'scene.xodr')}],
  'existing_evidence':assignment['existing_evidence'],
  'runtime_uncertainties':['native sign/signal authority and phase','weather/ice or snow physical state',
   'full actor/body physical motion and visibility','synthetic public-way context']}
 write(folder/'case-plan.json',plan)
 base={'actor':assignment['actor'],'law_id':assignment['law_id'],'cell_id':assignment['cell_id'],'mode':mode,
  'supported_case_ids':[c['case_id'] for c in cases],'required_atoms':['kin.position','kin.heading','kin.speed'],
  'authored_test_context':{'core_assumptions':[['asm.public_highway',True]],
   'public_highway_provenance':'synthetic authored setup, not jurisdictional proof','scenario':assignment['branch']},
  'public_way_road_ids':[],'target_speed_mps':5.,'max_ticks':500,
  'route_last_index':132 if mode in ('signal_amber','signal_dark') else 300,
  'cameras':[{'width':1920,'height':1080,'x':-8,'y':0,'z':35,'pitch':-80,'yaw':0},
   {'width':1280,'height':720,'x':2,'y':0,'z':4,'pitch':-10,'yaw':0},
   {'width':1280,'height':720,'x':-4,'y':-8,'z':5,'pitch':-12,'yaw':25},
   {'width':1280,'height':720,'x':7,'y':-3,'z':8,'pitch':-35,'yaw':90}]}
 write(folder/'config.json',dict(base,case=cases[0],selected_case_id=cases[0]['case_id']))
 common=['runner.py','analyze.py','scene.xodr','tests/test_scenario.py']
 def construction(case):
  files=[{'path':n,'content':(folder/n).read_text(),'source':str((folder/n).relative_to(REPO))} for n in common]
  files.append({'path':'config.json','content':json.dumps(dict(base,case=case,selected_case_id=case['case_id']),indent=2)+'\n'})
  return {'case_id':case['case_id'],'cell_id':assignment['cell_id'],'actor':assignment['actor'],'entrypoint':'runner.py',
   'recording_description':desc,'measurement_plan':'Original native road/device/weather, actor/body and motion measurements for '+mode,
   'static_checks':['OpenDRIVE structure','original frame/channel join','source camera decode'],
   'termination_rules':['measured route endpoint or maximum 500 original ticks'],
   'mechanisms':['native controller '+mode,'PipelineCapture original source','FrameMap','four RGB cameras','world restore'],
   'files':files}
 write(folder/'construction.json',construction(cases[0]));entries=[]
 for case in cases:
  cp=folder/'constructions'/(case['case_id']+'.json');write(cp,construction(case))
  acquisition={n:{'entrypoint':'runner.py','method':'original actor/map/control acquisition and saved-only analysis',
   'evidence':['trace.jsonl','capture/evidence.jsonl','channels/'+n+'.jsonl']} for n in ('kin.position','kin.heading','kin.speed','source_observations')}
  entries.append({'case_id':case['case_id'],'kind':'capability','construction':str(cp.relative_to(folder)),
   'construction_sha256':sha(cp),'measurement_procedure':{'entrypoint':'analyze.py','output_schema':'partition04-capability-report-v1'},
   'acquisition':acquisition})
 write(folder/'execution-manifest.json',{'format':'worker-execution-manifest-v1','assignment_id':aid,
  'runtime_manifest_sha256':sha(RUNTIME/'SOURCE-MANIFEST.json'),'cases':entries})
 print(aid,mode,len(cases))
if __name__=='__main__':
 for aid in PARTITION:build(aid)
