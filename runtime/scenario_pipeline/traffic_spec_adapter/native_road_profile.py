"""Source-surveyed single road surfaces and mesh-resolution crest geometry.

User grade/curvature belong to user_road_profile. This module supplies neither
region scalars nor midpoint-grade patches. A crest strip represents a surveyed
maximum at the declared mesh resolution, never a statutory near-crest extent.
"""
import ast,hashlib,json,math,shlex,sys,xml.etree.ElementTree as ET
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def derivative(e,s):
 d=s-float(e.get('s'));return float(e.get('b',0))+2*float(e.get('c',0))*d+3*float(e.get('d',0))*d*d

def _lane_layout(road):
 sections=road.findall('./lanes/laneSection')
 if len(sections)!=1 or float(sections[0].get('s'))!=0:raise ValueError('One complete source lane section required')
 centers={};totals={}
 for side,sign in [('left',-1),('right',1)]:
  lanes=sorted(sections[0].findall(side+'/lane'),key=lambda lane:abs(int(lane.get('id'))));total=0.
  if [abs(int(l.get('id')))for l in lanes]!=list(range(1,len(lanes)+1)):raise ValueError('Noncontiguous source lanes')
  for lane in lanes:
   ident=int(lane.get('id'));widths=lane.findall('width')
   if ident*sign>=0 or lane.get('type')!='driving' or len(widths)!=1:raise ValueError('Uncertified lane type or side')
   w=widths[0];width=float(w.get('a','nan'))
   if not math.isfinite(width)or width<=0 or any(float(w.get(k,'nan'))!=0 for k in ['sOffset','b','c','d']):raise ValueError('Unsupported source width')
   if any(float(h.get(k,'0'))!=0 for h in lane.findall('height')for k in ['inner','outer']):raise ValueError('Uncertified raised lane')
   centers[ident]=sign*(total+width/2);total+=width
  totals[side]=total
 return centers,(-totals['right'],totals['left'])

def single_profile_surface_road(root):
 roads=root.findall('road')
 if len(roads)!=1:raise ValueError('Unique source road required; independent height layers unproved')
 road=roads[0];length=float(road.get('length'));gs=road.findall('./planView/geometry')
 if not math.isfinite(length)or length<=0 or len(gs)!=1:raise ValueError('One complete source reference required')
 g=gs[0]
 if any(float(g.get(k,'0'))!=0 for k in ['s','x','y','hdg'])or float(g.get('length'))!=length:raise ValueError('Unsupported source reference frame')
 if g.find('line')is None:
  a=g.find('arc');k=float(a.get('curvature','nan'))if a is not None else float('nan')
  if not math.isfinite(k)or not k or abs(k*length)>=2*math.pi:raise ValueError('Unsupported or looping source curve')
  _,bounds=_lane_layout(road)
  if max(abs(v)for v in bounds)*abs(k)>=1:raise ValueError('Source curve cross-section folds')
 for modifier in road.findall('./lateralProfile/*'):
  if modifier.tag not in ['superelevation','crossfall']or any(float(modifier.get(k,'0'))!=0 for k in 'abcd'):raise ValueError('Uncertified lateral height layer')
 _lane_layout(road)
 if any(float(off.get(k,'0'))!=0 for off in road.findall('./lanes/laneOffset')for k in 'abcd'):raise ValueError('Unsupported source lane offset')
 elev=road.findall('./elevationProfile/elevation');starts=[float(e.get('s'))for e in elev]
 if not starts or starts[0]!=0 or starts[-1]>length or any(not math.isfinite(v)for v in starts)or any(a>=b for a,b in zip(starts,starts[1:])):raise ValueError('Invalid source elevation domain')
 for e in elev:
  if any(k not in e.attrib or not math.isfinite(float(e.get(k)))for k in 'abcd'):raise ValueError('Incomplete source elevation')
 for a,b in zip(elev,elev[1:]):
  d=float(b.get('s'))-float(a.get('s'));terms=[float(a.get(k))*d**i for i,k in enumerate('abcd')];target=float(b.get('a'));u=sys.float_info.epsilon/2;bound=(16*u/(1-16*u))*(sum(abs(v)for v in terms)+abs(target))
  if not math.isfinite(sum(terms))or not math.isfinite(bound)or abs(sum(terms)-target)>bound:raise ValueError('Discontinuous source elevation')
 return int(road.get('id'))

def _xy(road,s,lateral):
 g=road.find('./planView/geometry');a=g.find('arc')
 if a is None:return [s,lateral]
 k=float(a.get('curvature'));return [(1/k-lateral)*math.sin(k*s),1/k-(1/k-lateral)*math.cos(k*s)]

def _proof(original,evidence=None):
 from .inventory_observations import Evidence
 original=Path(original)
 ev=evidence if evidence is not None else Evidence(original.parent)
 if not(original/'native_hill_surface_survey.json').is_file():
  if 'evidence/native_hill_surface_survey.json'in ev.expected:raise ValueError('Missing declared surface survey')
  return None
 for name in ['road.xodr','native_hill_surface_survey.json','construction.json']:
  if ev.path(name)is None:raise ValueError('Unbound source surface evidence: '+name)
 construction=json.loads((original/'construction.json').read_text());files={f['path']:f['content']for f in construction['files']};entry=construction.get('entrypoint','runner.py');names=[v for v in shlex.split(entry)if v in files and v.endswith('.py')]
 if len(names)!=1:raise ValueError('Unique frozen generator entrypoint required')
 builder=ev.path(names[0])
 if builder is None or hashlib.sha256(files[names[0]].encode()).hexdigest()!=sha(builder):raise ValueError('Unbound original generator bytes')
 path=ev.path('road.xodr');road_id=single_profile_surface_road(ET.parse(path).getroot());road=ET.parse(path).getroot().find('road');survey=json.loads((original/'native_hill_surface_survey.json').read_text())
 if survey.get('native_map_sha256')!=sha(path):raise ValueError('Survey belongs to another source map')
 packet_path=original/'native_road_profile.json'
 if not packet_path.is_file()and 'evidence/native_road_profile.json'in ev.expected:raise ValueError('Missing declared surface metadata')
 if packet_path.is_file():
  if ev.path('native_road_profile.json')is None:raise ValueError('Unbound original surface metadata')
  packet=json.loads(packet_path.read_text())
  if packet['map_sha256']!=sha(path)or packet['survey_sha256']!=sha(original/'native_hill_surface_survey.json')or packet['instrumentation_sha256']!=sha(builder):raise ValueError('Surface metadata provenance mismatch')
  width=packet['crest_ridge_mesh_width_m']
 else:
  calls=[n for n in ast.walk(ast.parse(builder.read_text()))if isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and n.func.attr=='OpendriveGenerationParameters']
  if len(calls)!=1:raise ValueError('Source mesh resolution not declared')
  params={v.arg:ast.literal_eval(v.value)for v in calls[0].keywords}
  if params.get('wall_height')!=0 or params.get('additional_width')!=0:raise ValueError('Uncertified additional generated geometry')
  width=params['vertex_distance']
 if type(width)not in(int,float)or not math.isfinite(width)or width<=0:raise ValueError('Invalid declared crest representation width')
 centers,bounds=_lane_layout(road);samples=survey['surface_samples'];stations=sorted({v['s_m']for v in samples})
 if len(stations)<3 or any(not math.isfinite(s)or not 0<=s<=float(road.get('length'))for s in stations):raise ValueError('Incomplete source survey')
 step=stations[1]-stations[0]
 if step<=0 or any(b-a!=step for a,b in zip(stations,stations[1:]))or len(samples)!=len(stations)*len(centers)or{(v['s_m'],v['lane_id'])for v in samples}!={(s,lane)for s in stations for lane in centers}:raise ValueError('Incomplete source cross-section survey')
 elev=road.findall('./elevationProfile/elevation')
 for v in samples:
  if type(v['lane_id'])is not int or type(v['s_m'])not in(int,float)or any(type(x)not in(int,float)or not math.isfinite(x)for x in v['native_waypoint_m'])or not math.isfinite(v['native_rotation_deg']['pitch']):raise ValueError('Nonfinite or malformed source survey')
  s=v['s_m'];e=max((e for e in elev if float(e.get('s'))<=s),key=lambda e:float(e.get('s')));d=s-float(e.get('s'));z=sum(float(e.get(k))*d**i for i,k in enumerate('abcd'));xy=_xy(road,s,-centers[v['lane_id']]);p=v['native_waypoint_m'];pitch=(math.radians(v['native_rotation_deg']['pitch'])+math.pi)%(2*math.pi)-math.pi
  if max(abs(p[0]-xy[0]),abs(p[1]+xy[1]))>.03 or abs(p[2]-z)>.02 or abs(pitch-(1 if v['lane_id']<0 else-1)*derivative(e,s))>.001:raise ValueError('Native waypoint contradicts source profile')
  hits=v['all_surface_hits']
  if any(len(h['position_m'])!=3 or any(type(x)not in(int,float)or not math.isfinite(x)for x in h['position_m'])for h in hits):raise ValueError('Nonfinite source ray')
  if not hits or max(h['position_m'][2]for h in hits)>z+.05 or not any(abs(h['position_m'][2]-z)<.05 for h in hits):raise ValueError('Native topmost surface contradicts source profile')
 peaks=[]
 for i,e in enumerate(elev):
  if float(e.get('d'))!=0:raise ValueError('Cubic crest derivation not supported')
  c=float(e.get('c'));start=float(e.get('s'));end=float(elev[i+1].get('s'))if i+1<len(elev)else float(road.get('length'))
  if c<0:
   peak=start-float(e.get('b'))/(2*c)
   if start<peak<end:
    if peak not in stations:raise ValueError('Physical crest lacks original peak survey')
    peaks.append(peak)
 if not peaks:return None
 return {'road':road,'road_id':road_id,'bounds':bounds,'peaks':peaks,'width':width,'source':str(original/'native_hill_surface_survey.json'),'sha256':sha(original/'native_hill_surface_survey.json'),'map_sha256':sha(path)}

def _surface_and_crests(original,proof,public=()):
 from shapely.geometry import Polygon
 from .geometry import static_map
 native,_,_=static_map(Path(original)/'road.xodr',include_non_driving=True,public_way_roads=set(public),partial=True)
 roadways=[r for r in native if r['kind']in('roadway','one_way_roadway')and r.get('boundary')]
 if len(roadways)!=1:raise ValueError('Unique source physical roadway surface required')
 # Use the shared exporter's canonical outline, including its declared
 # precision, rather than independently unioning rounded lane rings.
 surface=Polygon([[round(v,6)for v in p]for p in roadways[0]['boundary']])
 if not surface.is_valid or surface.geom_type!='Polygon'or surface.interiors:raise ValueError('Source surface is not one simple height sheet')
 shapes=[];lo,hi=proof['bounds']
 for station in proof['peaks']:
  a=station-proof['width']/2;b=station+proof['width']/2;shape=Polygon([_xy(proof['road'],a,lo),_xy(proof['road'],b,lo),_xy(proof['road'],b,hi),_xy(proof['road'],a,hi)]).intersection(surface)
  if not shape.is_valid or shape.geom_type!='Polygon'or shape.area<=0:raise ValueError('Invalid source crest strip')
  adjustment=0.
  if not surface.covers(shape):
   # Intersection is a subset by construction. Compensate only coordinate
   # roundoff, then require exact containment; no physical-distance epsilon.
   adjustment=64*sys.float_info.epsilon*max(1.,*(abs(v)for v in surface.bounds+shape.bounds))
   if shape.difference(surface).area>adjustment*shape.length:raise ValueError('Source intersection exceeds coordinate roundoff')
   shape=shape.buffer(-adjustment,join_style=2)
   if shape.is_empty or not shape.is_valid or shape.geom_type!='Polygon'or not surface.covers(shape):raise ValueError('Source crest containment remains unproved')
  proof.setdefault('roundoff_adjustments_m',{})[station]=adjustment
  shapes.append((station,shape))
 return native,surface,shapes

def apply(original,telemetry,regions,polygons):
 proof=_proof(original)
 if proof is None:return None
 _,_,crests=_surface_and_crests(original,proof);out=[]
 for station,shape in crests:
  ident=max((r['id']for r in regions),default=0)+1;regions.append({'id':ident,'kind':'crest','boundary':[list(p)for p in list(shape.exterior.coords)[:-1]]});polygons[ident]=shape;out.append({'region_id':ident,'station_m':station,'mesh_representation_width_m':proof['width'],'coordinate_roundoff_adjustment_m':proof['roundoff_adjustments_m'][station],'legal_near_extent':None})
 return {'source':proof['source'],'sha256':proof['sha256'],'physical_crests':out,'scope':'Source-surveyed physical maxima at declared mesh resolution. No region-grade estimate or statutory near extent.'}

def source_surface_certificate(evidence,regions,fields):
 from shapely.geometry import Polygon
 proof=_proof(evidence.base,evidence)
 if proof is None:return None
 public={proof['road_id']}if any('highway'in v.get('_verified_structure_kinds',())for v in fields.values())else set();native,surface,crests=_surface_and_crests(evidence.base,proof,public);bindings={};crest_fields={};additions=[]
 for station,shape in crests:
  matches=[r for r in regions if r['kind']=='crest'and r.get('boundary')and Polygon(r['boundary']).equals(shape)]
  if len(matches)>1:raise ValueError('Duplicate source crest identities')
  if not matches:
   if any(r['kind']=='crest'for r in regions):raise ValueError('Existing crest contradicts source geometry')
   ident=max([r['id']for r in regions+additions],default=0)+1;r={'id':ident,'kind':'crest','boundary':[list(p)for p in list(shape.exterior.coords)[:-1]]};additions.append(r)
  else:r=matches[0]
  crest_fields[r['id']]={'_source_road_ids':[proof['road_id']],'_verified_structure_kinds':['crest']};bindings[r['id']]={'kind':'crest','shape':shape}
 for r in regions:
  if r['id']in bindings or not r.get('boundary'):continue
  value=fields.get(r['id'],{});kind=r['kind'];source_owned=(value.get('_source_road_ids')==[proof['road_id']]or value.get('_lane_source',{}).get('road_id')==proof['road_id']or value.get('_centre_line_source',{}).get('road_id')==proof['road_id']);owned=source_owned and kind in value.get('_verified_structure_kinds',())
  if not owned and kind in value.get('_verified_structure_kinds',()):
   owned=any(v['kind']==kind and v.get('boundary')and Polygon(r['boundary']).equals(Polygon(v['boundary']))for v in native)
  if kind=='highway'and not owned:continue
  if not owned:continue
  shape=Polygon(value.get('boundary',r['boundary']))
  roundoff=64*sys.float_info.epsilon*max(1.,*(abs(v)for v in surface.bounds+shape.bounds))
  # This binds height scope, not geometry identity. The same-frame scope
  # consumer still requires exact containment of each actual body overlap.
  if shape.is_valid and shape.area>0 and shape.difference(surface).area<=roundoff*shape.length:bindings[r['id']]={'kind':kind,'shape':shape}
 return {'surface':surface,'bindings':bindings,'fields':crest_fields,'additions':additions,'source':proof['source'],'sha256':proof['sha256'],'road_id':proof['road_id'],'coordinate_precision_decimals':6}
