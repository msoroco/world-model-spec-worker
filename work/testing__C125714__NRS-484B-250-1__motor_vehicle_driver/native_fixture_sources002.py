"""Author Native-shaped SOFTWARE fixture acquisition for migration002 tests.

Never call this on an actual Native recording. It creates diagnostic raw source
files/context, tests selected prepare_saved, then removes its derived outputs so
the real saved-processing invocation must regenerate them after owner release.
"""
import ast, copy, hashlib, importlib.util, json, math
from pathlib import Path


def _read(path,default=None):
 p=Path(path)
 return json.loads(p.read_text()) if p.is_file() else copy.deepcopy(default)
def _rows(path):
 p=Path(path)
 return [json.loads(s) for s in p.read_text().splitlines() if s.strip()] if p.is_file() else []
def _write(path,value):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,indent=2)+'\n')
def _write_rows(path,rows):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def _get(value,path,default=None):
 try:
  for key in path.split('.'):value=value[key]
  return value
 except (KeyError,TypeError):return default

def _box(point,yaw=0,length=4,width=1.6):
 x,y=point[:2];a=math.radians(yaw);c,s=math.cos(a),math.sin(a)
 return [[x+dx*c-dy*s,y+dx*s+dy*c,z] for z in (0,1.5) for dx,dy in [(-length/2,-width/2),(-length/2,width/2),(length/2,width/2),(length/2,-width/2)]]

def _preparation(root,source):
 if source is None:
  path=Path(root)/'analyze.py'
  if not path.is_file():raise ValueError('Supply selected prepare_saved source or materialized analyzer')
  tree=ast.parse(path.read_text());function=next((n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='prepare_saved'),None)
  if function is None:raise ValueError('Selected analyzer has no saved-source preparation')
  source=ast.unparse(function)+'\n'
 tree=ast.parse(source);outputs=[]
 for node in ast.walk(tree):
  if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Attribute) or node.func.attr not in ('write_text','open'):continue
  if node.func.attr=='open' and (not node.args or not isinstance(node.args[0],ast.Constant) or not any(c in str(node.args[0].value) for c in 'wxa')):continue
  value=node.func.value
  if isinstance(value,ast.BinOp) and isinstance(value.op,ast.Div) and isinstance(value.left,ast.Name) and value.left.id=='out' and isinstance(value.right,ast.Constant) and isinstance(value.right.value,str):
   if value.right.value not in outputs:outputs.append(value.right.value)
 namespace={};exec(source,namespace)
 return source,namespace['prepare_saved'],outputs

def make_native_sources(root,cfg,preparation_source=None,strict=True):
 root=Path(root)
 marker=_read(root/'acquisition-provenance.json',{})
 if not (root/'fixture-provenance.json').is_file() and marker.get('diagnostic_fixture') is not True:
  raise ValueError('Native fixture authoring requires an explicit diagnostic marker; never rewrite a real capture')
 source,prepare,derived=_preparation(root,preparation_source)
 packet=_read(root/'case_observation.json',{})
 traces=_rows(root/'trace.jsonl');mapping=_rows(root/'video_frames.jsonl')
 if not traces or len(traces)!=len(mapping):raise ValueError('Diagnostic raw trace/frame-map sources required')
 for r,m in zip(traces,mapping):
  if r['frame']!=m['carla_frame'] or abs(r['time_s']-m['time_s'])>1e-4:raise ValueError('Diagnostic original trace timestamps differ')
 law=cfg['law_id']
 # The accepted truck projection deliberately rejects extrapolation outside
 # x0..1500. Use its actual straight-road support while preserving all gaps.
 if law=='NRS-484B-127-2':
  trucks=_rows(root/'truck_history.jsonl')
  vertices=[v for r in trucks for key in ('ego_vertices_m','lead_vertices_m','entrant_vertices_m') for v in r.get(key,[])]
  if vertices and min(v[0] for v in vertices)<0:
   for r in trucks:
    for key in ('ego_vertices_m','lead_vertices_m','entrant_vertices_m'):
     for v in r.get(key,[]):v[0]+=300
   _write_rows(root/'truck_history.jsonl',trucks)
   for t in traces:
    t['position_m'][0]+=300
    if isinstance(t.get('position'),dict):t['position']['x']+=300
   _write_rows(root/'trace.jsonl',traces)
 geometry=_read(root/'road_geometry.json',{})
 old_surface=_read(root/'surface_context.json',{});old_alley=_read(root/'alley_context.json',{});old_posted=_read(root/'posted_speed_context.json',{})
 cal=_read(root/'environment_calibration.json',{})
 context={
  'native_map_name':'diagnostic-native-format-map; software fixture, not an actual recording',
  'native_landmarks':old_posted.get('native_landmarks',[]),
  'landmark_ids':[str(packet.get('direction_sign',{}).get('native_id',220001))],
  'aisle_inventory':old_alley.get('native_aisle_markings',[]),
  'cal':cal,
  'surface_authoring':old_surface.get('surface_authoring',{'ice_or_snow':False,'basis':'Diagnostic authored asphalt layer inventory; no Native acceptance'}),
  'geometry':geometry,
  'diagnostic_fixture':True,
  'source_kind':'software_authored_native_style',
  'physical_acceptance_claimed':False,
 }
 raw_paths=set()
 def wr(name,rows):_write_rows(root/name,rows);raw_paths.add(name)
 def wj(name,value):_write(root/name,value);raw_paths.add(name)
 # Fill a complete original-shaped per-tick body stream where the legacy
 # diagnostic recipe supplied only an aggregate. Existing primary motion wins.
 bodies=_rows(root/'body_history.jsonl')
 if not bodies and law in {'NRS-484B-127-1','NRS-484B-600-1e','NRS-484B-400-2a','NRS-484B-400-2b','NRS-484B-253','NRS-484B-250-1','NRS-484B-250-2','NRS-484B-227-1','NRS-484B-600-1c','NRS-484B-220-1','NRS-484B-413-2','NRS-484B-600-1a'}:
  for r in traces:
   point=r.get('position_m',[r.get('position',{}).get('x',0),r.get('position',{}).get('y',0),0]);bodies.append({'frame':r['frame'],'time_s':r['time_s'],'body_vertices_m':_box(point,r.get('heading_deg',0)),'road_id':1,'lane_id':-1,'control':r.get('control',{}),'camera_originals':{}})
  wr('body_history.jsonl',bodies)
 if law in ('NRS-484B-250-1','NRS-484B-250-2'):
  crossing=_rows(root/'crossing_history.jsonl')
  if not crossing:crossing=[{'frame':r['frame'],'time_s':r['time_s'],'ego_vertices_m':b['body_vertices_m']} for r,b in zip(traces,bodies)]
  opposite=cfg.get('opposite_other',False);left=cfg.get('other_makes_left',False)
  control=packet.get('official_control_inventory',[])
  for i,(r,t) in enumerate(zip(crossing,traces)):
   progress=i/(len(crossing)-1) if len(crossing)>1 else 0
   if opposite:
    other=[20-40*progress,1.75]
    if left and progress>0.5:other=[1.75,-40*(progress-.5)]
   else:other=[1.75,(-5+40*progress) if cfg.get('other_second_intersection') else (-20+40*progress)]
   r.update(ego_speed_mps=t.get('speed_mps',5),other_speed_mps=5,other_vertices_m=_box(other),official_controls=copy.deepcopy(control))
   r.setdefault('frame',t['frame']);r.setdefault('time_s',t['time_s']);r.setdefault('ego_vertices_m',bodies[i]['body_vertices_m'])
  wr('crossing_history.jsonl',crossing)
 elif law=='NRS-484B-227-1':
  names=('right_roadway_polygon','opposing_roadway_polygon','barrier_polygons','opening_polygon','opening_width_m')
  if not all(name in geometry for name in names):geometry={name:copy.deepcopy(packet[name]) for name in names}
  context['geometry']=geometry;wj('road_geometry.json',geometry)
 elif law=='NRS-484B-413-2':
  geometry.update(business_district_frontage_m=packet.get('frontage_m',120),business_use_frontage_m=packet.get('business_use_frontage_m',0),district_source=packet.get('district_source','Diagnostic authored district context'),loading_zone_polygon=packet.get('zone_polygon',[[-50,-10],[-25,-10],[-25,-7],[-50,-7]]),loading_zone_designation_source=packet.get('zone_designation_source','Diagnostic authored loading-zone object'))
  context['geometry']=geometry;wj('road_geometry.json',geometry)
  course=cfg.get('course','right_turn');signals=[]
  for i,(b,t) in enumerate(zip(bodies,traces)):
   if course=='change_lane':
    b.setdefault('road_id',1);b.setdefault('lane_id',-2 if i==len(bodies)-1 else -1)
   else:
    connector=13 if course=='left_turn' else 14;departure=4 if course=='left_turn' else 3;b.setdefault('road_id',1 if i==0 else connector if i<len(bodies)-1 else departure);b.setdefault('lane_id',-1)
   bits=(packet.get('indicator_rows') or [{}])[min(i,len(packet.get('indicator_rows') or [{}])-1)].get('lamp_bits',1)
   signals.append({'frame':t['frame'],'time_s':t['time_s'],'right_indicator_api_bit':bool(bits),'body_roi_photometry':{'camera_frame':t['frame'],'photometry':{'mean_luminance':80 if bits else 20}},'road_id':b['road_id'],'lane_id':b['lane_id'],'position_m':t['position_m']})
  wr('body_history.jsonl',bodies);wr('signal_history.jsonl',signals)
 elif law=='NRS-484B-600-1a':
  if not cal:raise ValueError('Actual retained calibration packet required in Native-style software fixture')
  # Use the actual retained original images; never author contrast outcomes.
  for sample in cal.get('samples',[]):
   for channel in ('rgb','instance'):
    p=root/sample[channel]['path']
    if not p.is_file() or _sha(p)!=sample[channel]['sha256']:raise ValueError('Original diagnostic calibration image missing or changed: '+sample[channel]['path'])
  motion=packet.get('motion_rows',[]);weather=packet.get('weather_rows',[]);rays=packet.get('sight_ray_samples',[]);traffic=packet.get('traffic_actor_inventory_by_frame',[]);other=[]
  for i,t in enumerate(traces):
   m=motion[min(i,len(motion)-1)] if motion else {};w=weather[min(i,len(weather)-1)] if weather else {};ray=rays[min(i,len(rays)-1)] if rays else {};actors=traffic[min(i,len(traffic)-1)].get('actors',[]) if traffic else []
   other.append({'frame':t['frame'],'time_s':t['time_s'],'other_speed_mps':m.get('other_speed_mps',5),'separation_m':m.get('separation_m',100),'weather':{'wetness':w.get('wetness_native',0),'fog_density':w.get('fog_density_native',cal.get('weather',{}).get('fog_density',2)),'precipitation':w.get('precipitation_native',0)},'traffic_actor_inventory':actors,'sight_ray_hit_count':ray.get('hit_count',0)})
  wr('other_motion.jsonl',other)
 # Capture-time context is a primitive snapshot, not a live Carla object. The
 # actual runner calls capture_context before restoration; this helper authors
 # only the analogous software fixture bytes.
 wj('acquisition-context.json',context)
 before={name:_sha(root/name) for name in raw_paths if name not in derived}
 removed=[]
 for name in derived:
  p=root/name
  if p.exists():p.unlink();removed.append(name)
 result=None;failure=None
 try:result=prepare(root)
 except Exception as error:
  failure={'error_type':type(error).__name__,'error':str(error)}
 finally:
  # Even a successful authoring self-test must not put precomputed law packets
  # into the sealed capture: selected saved analysis must create them later.
  for name in derived:
   p=root/name
   if p.exists():p.unlink()
 if any(_sha(root/name)!=digest for name,digest in before.items()):raise ValueError('Saved preparation rewrote raw diagnostic acquisition')
 report={'format':'worker-native-style-fixture-sources-v002','case_id':cfg['selected_case_id'],'raw_source_hashes':before,'derived_outputs':derived,'removed_before_seal':True,'preparation_source_sha256':hashlib.sha256(source.encode()).hexdigest(),'authoring_preparation_test':result,'derivation_failure':failure,'diagnostic_fixture':True,'physical_acceptance_claimed':False}
 if failure and strict:raise ValueError('Fresh Native-style saved preparation failed: '+failure['error'])
 return report
