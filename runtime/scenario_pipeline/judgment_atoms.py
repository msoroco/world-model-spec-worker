"""Current ontology values from delivered scenes and source-bound actor roles."""
import hashlib
import json
import math
from pathlib import Path
from traffic_spec_adapter import adapter
from traffic_spec_adapter.geometry import body
from traffic_spec_adapter.atom_contract import _structure_kind_matches

LIBRARY=Path(adapter.__file__).resolve().parents[2]/'repo_prep/nevada_sydney/pipeline/traffic-spec-agent/library'
ATOMS=frozenset(adapter.atom_ids(LIBRARY))
UNITS={'kin.time':'ms','kin.position':'m','kin.heading':'1','kin.extent':'m',
 'kin.velocity':'m/s','kin.speed':'m/s','kin.accel_longitudinal':'m/s^2',
 'kin.yaw_rate':'deg/s','kin.path_length':'m','kin.steer_angle':'deg',
 'kin.throttle':'1','kin.service_brake':'1','kin.parking_brake':'Boolean',
 'st.grade':'1','st.curvature':'1/m','st.lane_width':'m','st.sight_distance':'m',
 'st.region_geometry':'m','rel.surface_gap':'m','rel.centre_distance':'m',
 'rel.visible':'Boolean','rel.occupies':'Boolean','sig.turn_indicator':'state','env.visibility':'m',
 'env.darkness':'Boolean','env.precipitation':'Boolean','env.wet_road':'Boolean',
 'env.ice_or_snow':'Boolean','ru.motor_vehicle':'Boolean','ru.pedestrian':'Boolean','ru.bicycle':'Boolean'}

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb')as stream:
  for chunk in iter(lambda:stream.read(1048576),b''):h.update(chunk)
 return h.hexdigest()

def ref(path):return {'path':str(Path(path)),'sha256':sha(path)}

def contract():
 core=LIBRARY/'splits/full/TrafficSpec/Core'
 docs=LIBRARY.parent/'ontology/ATOMS.md'
 return {'atom_ids':ref(core/'Vocab/Ontology/Ids.lean'),'definitions':ref(core/'Vocab/Atoms.lean'),'documentation':ref(docs)}

def finite(value):return type(value)in(int,float)and math.isfinite(value)

def _vector(value,n):return isinstance(value,list)and len(value)==n and all(finite(x)for x in value)

def footprint(user):
 k=user.get('kin',{});p,h,e=(k.get(x)for x in('position','heading','extent'))
 if not(_vector(p,2)and _vector(h,2)and _vector(e,3))or min(e)<0:return None
 length=math.hypot(*h)
 if not length:return None
 hx,hy=(x/length for x in h)
 from shapely.geometry import Polygon
 return Polygon([[p[0]+a*e[0]*hx-b*e[1]*hy,p[1]+a*e[0]*hy+b*e[1]*hx]for a,b in[(1,1),(-1,1),(-1,-1),(1,-1)]])

def _body_matches(actor,user):
 points,heading=actor.get('body_vertices_m'),actor.get('heading_deg')
 if not(isinstance(points,list)and len(points)==8 and all(_vector(p,3)for p in points)and finite(heading)):return False
 centre,extent,_=body(points,heading);h=math.radians(-heading);actual=user.get('kin',{})
 # These are the two existing shared export policies, not a new physical tolerance.
 exact=(centre,extent,[math.cos(h),math.sin(h)])
 rounded=tuple(adapter.rounded(v)for v in exact)
 saved=tuple(actual.get(k)for k in('position','extent','heading'))
 return saved==exact or saved==rounded

class Sources:
 """Only source identities are joined; all emitted values come from the trace."""
 def __init__(self,folder):
  self.folder=Path(folder);self.sources=[];self.streams={};self.identity={};index=self.folder/'evidence-checksums.json';self.checks=json.loads(index.read_text())if index.is_file()else{}
  for name in('actual_scene_identity.json',):
   p=self.folder/'evidence'/name
   if p.is_file():self.identity=json.loads(p.read_text());self.sources.append(self.source_ref(p))
  for key,name in [('capture','capture/evidence.jsonl'),('supplement','traffic_spec/supplementary_evidence.jsonl'),('motion','native-motion.jsonl')]:
   p=self.folder/'evidence'/name
   if p.is_file():self.streams[key]=p.open();self.sources.append(self.source_ref(p))
  if'motion'not in self.streams:
   p=self.folder/'evidence/synchronized_motion_records.jsonl'
   if p.is_file():self.streams['motion']=p.open();self.sources.append(self.source_ref(p))
  if'motion'not in self.streams:
   p=self.folder/'evidence/interaction_history.jsonl'
   if p.is_file():self.streams['motion']=p.open();self.sources.append(self.source_ref(p))
 def source_ref(self,path):
  actual=ref(path);relative=str(path.relative_to(self.folder));expected=self.checks.get(relative)
  if expected is not None and actual['sha256']!=expected:raise ValueError('Registered actor source hash differs: '+relative)
  return {'path':relative,'sha256':actual['sha256']}
 def close(self):
  for stream in self.streams.values():stream.close()
 def frame(self,scene):
  rows={}
  for key,stream in self.streams.items():
   line=stream.readline()
   if not line:raise ValueError('Source stream ends before delivered trace: '+key)
   rows[key]=json.loads(line)
  motion=rows.get('motion',{})
  if isinstance(motion.get('value'),dict):
   wrapper=motion;motion=dict(wrapper['value'])
   if finite(wrapper.get('time_s')):
    if 'time_s'in motion and motion['time_s']!=wrapper['time_s']:raise ValueError('Wrapped motion clock differs')
    motion['time_s']=wrapper['time_s']
  supplement=rows.get('supplement',{})
  if 'world_scene_t'in supplement and supplement['world_scene_t']!=scene['t']:raise ValueError('Supplement clock differs from delivered trace')
  capture=rows.get('capture',supplement.get('evidence',{}))
  times=[v for v in(capture.get('recording_time_s'),motion.get('time_s'))if finite(v)]
  if times and any(round(t*1000)!=scene['t']for t in times):raise ValueError('Actor source clock differs from delivered trace')
  if capture and motion and capture.get('original_frame')!=motion.get('frame'):raise ValueError('Actor source frame mismatch')
  users={u['track']:u for u in scene.get('users',[])}
  if len(users)!=len(scene.get('users',[])):raise ValueError('Duplicate delivered actor')
  roles={'subject':{scene['subject']},'ego':{scene['subject']},'all_recorded':set(users)}
  named=[]
  states=motion.get('states',{})
  if isinstance(states,dict):named.extend((k,v)for k,v in states.items()if isinstance(v,dict)and type(v.get('actor_id'))is int)
  named.extend((k,v)for k,v in motion.items()if isinstance(v,dict)and type(v.get('actor_id'))is int)
  participants=capture.get('original_observations',{}).get('participants',[])
  for actor in participants:
   if not isinstance(actor,dict):continue
   role=actor.get('blueprint_attributes',actor.get('attributes',{})).get('role_name')
   if isinstance(role,str):named.append((role,actor))
  verified={}
  for role,actor in named:
   ident=actor['actor_id']
   if ident in users and _body_matches(actor,users[ident]):
    roles.setdefault(role,set()).add(ident);verified[ident]=actor
  # This producer names the through actor in history, while its synchronized
  # capture supplies heading. Join exact IDs and complete native body vertices.
  through=motion.get('through',{})
  if isinstance(through,dict):
   ident=through.get('actor_id')
   if ident in verified and through.get('body_vertices_m')==verified[ident].get('body_vertices_m'):
    roles.setdefault('through',set()).add(ident)
  extras=motion.get('extra_traffic')
  if isinstance(extras,list):
   ids=[a.get('actor_id')for a in extras if isinstance(a,dict)]
   if len(ids)==len(extras)and len(set(ids))==len(ids)and all(type(i)is int and i in users and _body_matches(a,users[i])for i,a in zip(ids,extras)):
    roles['recorded_extras']=set(ids)
  for role,key in [('leader','lead_actor_id'),('other','other_actor_id')]:
   ident=self.identity.get(key)
   if ident in verified:
    if role=='leader':
     attributes=verified[ident].get('blueprint_attributes',verified[ident].get('attributes',{}));tag=attributes.get('role_name','')
     if 'lead'not in tag.split('_')and ident not in roles.get('leader',set()):continue
    roles.setdefault(role,set()).add(ident)
  counterparts=roles.get('leader',set())|roles.get('other',set())
  if counterparts:roles['counterpart']=counterparts
  if self.identity.get('subject_actor_id',scene['subject'])!=scene['subject']:raise ValueError('Original subject differs from trace')
  if capture and capture.get('actor_id')!=scene['subject']:raise ValueError('Capture subject differs from trace')
  if roles.get('ego')!={scene['subject']}:raise ValueError('Source ego role differs from trace')
  return {'roles':roles,'supplement':supplement,'capture':capture,'motion':motion,'users':users}
 def finish(self):
  if any(stream.readline()for stream in self.streams.values()):raise ValueError('Source stream has additional scenes')

def actors(context,role):
 found=context['roles'].get(role,set())
 if role=='all_recorded'or role=='recorded_extras'and role in context['roles']:return sorted(found)
 if len(found)!=1:raise ValueError('source_actor_role_not_unique:'+str(role))
 return list(found)

def value(scene,user,request,context,region=None,other=None):
 q=request['quantity'];k=user.get('kin',{})
 if q=='kin.time':v=scene['t']
 elif q.startswith('kin.'):v=k.get(q.split('.')[1])
 elif q=='st.grade':
  v=user.get('road_grade')
  if not _vector(k.get('heading'),2)or not math.hypot(*k['heading']):v=None
 elif q=='st.curvature':v=user.get('road_curvature')
 elif q.startswith('env.'):v=scene.get('env',{}).get(q.split('.')[1])
 elif q.startswith('sig.'):v=user.get('sig',{}).get(q.split('.')[1])
 elif q.startswith('ru.'):
  tag=q.split('.')[1];classes=user.get('classes');v=None if tag in user.get('unobserved_classes',[])or not isinstance(classes,list)else tag in classes
 elif q=='st.lane_width':v=(region or{}).get('lane',{}).get('width')
 elif q=='st.sight_distance':v=(region or{}).get('sight_distance')
 elif q=='st.region_geometry':v=(region or{}).get('boundary')
 elif q=='rel.visible':v=next((r for r in scene.get('relations',[])if r.get('a')==user['track']and r.get('b')==other['track']),{}).get('visible')
 elif q=='rel.occupies':v=None if user['track']not in scene.get('occupancy_observed',[])else[user['track'],region['id']]in scene.get('occupies',[])
 elif q=='rel.centre_distance':
  a,b=k.get('position'),other.get('kin',{}).get('position');v=math.dist(a,b)if _vector(a,2)and _vector(b,2)else None
 elif q=='rel.surface_gap':
  pair=next((r for r in scene.get('relations',[])if r.get('a')==user['track']and r.get('b')==other['track']),{})
  v=pair.get('surface_gap')
  if v is None:
   a,b=footprint(user),footprint(other)
   if a is None or b is None:return None
   if a.intersects(b):v=[0.,0.]
   else:
    from shapely.ops import nearest_points
    pa,pb=nearest_points(a,b);dx,dy=pb.x-pa.x,pb.y-pa.y;h=k.get('heading');n=math.hypot(*h);hx,hy=h[0]/n,h[1]/n
    v=[abs(dx*hx+dy*hy),abs(-dx*hy+dy*hx)]
  if not _vector(v,2)or min(v)<0:return None
 else:raise ValueError('Atom reader not implemented: '+q)
 if v is None:return None
 if q in('kin.position','kin.heading','kin.velocity','rel.surface_gap'):
  if not _vector(v,2):raise ValueError('Atom requires a two-vector: '+q)
 elif q=='kin.extent':
  if not _vector(v,3)or min(v)<0:raise ValueError('Extent requires three nonnegative half sizes')
 elif q=='st.region_geometry':
  if not isinstance(v,list)or len(v)<3 or not all(_vector(p,2)for p in v):raise ValueError('Region boundary unavailable')
 elif q=='sig.turn_indicator':
  if v not in('off','left','right'):raise ValueError('Invalid ontology turn indicator state')
 elif UNITS[q]=='Boolean':
  if type(v)is not bool:raise ValueError('Atom requires Boolean: '+q)
 elif not finite(v):raise ValueError('Atom requires finite scalar: '+q)
 return v

def regions(scene,user,request):
 candidates=scene.get('structures',[])
 if request.get('region_kind'):candidates=[r for r in candidates if _structure_kind_matches(r.get('kind'),request['region_kind'])]
 if request['quantity']=='st.lane_width':candidates=[r for r in candidates if isinstance(r.get('lane'),dict)]
 if request.get('region_scope')=='occupied':
  if user['track']not in scene.get('occupancy_observed',[]):raise ValueError('occupancy_not_observed_for_region_binding')
  occupied={r for a,r in scene.get('occupies',[])if a==user['track']};candidates=[r for r in candidates if r['id']in occupied]
 return candidates
