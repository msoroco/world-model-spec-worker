"""Current per-user local source road grade/curvature; no region scalar API."""
import math,xml.etree.ElementTree as ET

def finite(value):return type(value)in(int,float)and math.isfinite(value)

def profile_at(road,station,position_native,heading_core):
 """Analytic horizontal plan and elevation derivatives at the bound position."""
 if not finite(station)or not 0<=station<=float(road.get('length')):return None,None,'station_outside_source'
 geometries=road.findall('./planView/geometry');active=[g for g in geometries if float(g.get('s'))<=station<=float(g.get('s'))+float(g.get('length'))]
 # At a seam use the right-hand source segment, with matching position below.
 if len(active)>1:active=[max(active,key=lambda g:float(g.get('s')))]
 if not active:return None,None,'missing_plan_geometry'
 g=active[0];ds=station-float(g.get('s'));theta=float(g.get('hdg'));x=float(g.get('x'));y=float(g.get('y'));arc=g.find('arc')
 if g.find('line')is not None:k=0.
 elif arc is not None:k=float(arc.get('curvature'))
 else:return None,None,'unsupported_plan_geometry'
 if not all(math.isfinite(v)for v in (ds,theta,x,y,k)):raise ValueError('Nonfinite source road geometry')
 if k:
  x+=(math.sin(theta+k*ds)-math.sin(theta))/k;y-=(math.cos(theta+k*ds)-math.cos(theta))/k;theta+=k*ds
 else:x+=ds*math.cos(theta);y+=ds*math.sin(theta)
 # OpenDRIVE XY is right-handed; retained CARLA body positions reflect Y.
 tangent=(math.cos(theta),math.sin(theta));dx=position_native[0]-x;dy=-position_native[1]-y
 if abs(dx*tangent[0]+dy*tangent[1])>1e-5:return None,None,'position_station_mismatch'
 lateral=-dx*tangent[1]+dy*tangent[0];jacobian=1-k*lateral
 if jacobian<=0:return None,None,'nonregular_road_offset'
 curvature=abs(k/jacobian)
 # Cross-slope modifies the surface gradient. Do not silently assume it zero.
 if any(any(float(m.get(c,'0'))!=0 for c in'abcd')for m in road.findall('./lateralProfile/*')):return None,curvature,'unsupported_cross_slope'
 elevations=road.findall('./elevationProfile/elevation')
 if not elevations:elevations=[];slope=0.
 else:
  starts=[float(e.get('s'))for e in elevations]
  if starts[0]!=0 or any(a>=b for a,b in zip(starts,starts[1:])):raise ValueError('Incomplete source elevation domain')
  candidates=[e for e in elevations if float(e.get('s'))<=station]
  if not candidates:return None,curvature,'missing_elevation'
  e=candidates[-1];d=station-float(e.get('s'));coeff=[float(e.get(c,'nan'))for c in'abcd']
  if not all(math.isfinite(v)for v in coeff):raise ValueError('Nonfinite source elevation')
  slope=coeff[1]+2*coeff[2]*d+3*coeff[3]*d*d
 if heading_core is None:return None,curvature,'heading_unobserved'
 if len(heading_core)!=2 or not all(finite(v)for v in heading_core):raise ValueError('Invalid observed horizontal heading')
 # Exported Core heading already uses OpenDRIVE XY; do not reflect it again.
 hx,hy=heading_core[0],heading_core[1];norm=math.hypot(hx,hy)
 if not norm:return None,curvature,'heading_unobserved'
 return slope*(hx*tangent[0]+hy*tangent[1])/(norm*jacobian),curvature,None

def compile_profiles(path):
 root=ET.parse(path).getroot();roads={int(r.get('id')):r for r in root.findall('road')}
 if len(roads)!=len(root.findall('road')):raise ValueError('Duplicate native source road')
 return roads

def project_user_profiles(scene,roads,bindings):
 """Both fresh and retained exporters use the same position/heading contract.

 Bindings are original source-validated unique physical Roadway assignments,
 not nearest-waypoint guesses. Missing/ambiguous binding remains unknown.
 """
 from shapely.geometry import Point,Polygon
 diagnostics=[]
 for user in scene.get('users',[]):
  user.pop('road_grade',None);user.pop('road_curvature',None)
  binding=bindings.get(str(user['track']),bindings.get(user['track']))
  if not binding:diagnostics.append({'track':user['track'],'reason':'roadway_binding_unknown'});continue
  ident=binding.get('roadway_id');candidates=binding.get('unique_Roadway_candidates')
  if candidates!=[ident]:diagnostics.append({'track':user['track'],'reason':'roadway_binding_ambiguous'});continue
  kin=user.get('kin',{});pos=kin.get('position');native=binding.get('position_native_m')
  if not isinstance(pos,list)or len(pos)!=2 or not all(finite(v)for v in pos)or not isinstance(native,list)or len(native)not in(2,3) or not all(finite(v)for v in native):diagnostics.append({'track':user['track'],'reason':'position_unknown'});continue
  if max(abs(pos[0]-native[0]),abs(pos[1]+native[1]))>1e-6:raise ValueError('User source body-centre position differs')
  region=next((r for r in scene.get('structures',[])if r['id']==ident),None)
  if region is None or region['kind']not in('roadway','one_way_roadway')or not region.get('boundary')or not Polygon(region['boundary']).covers(Point(pos)):raise ValueError('Unique source Roadway does not contain user position')
  road=roads.get(binding.get('native_road_id'))
  if road is None:raise ValueError('Bound native road unavailable')
  observed=kin.get('heading');source_heading=binding.get('heading_core_observed')
  if observed is not None and source_heading is not None and max(abs(a-b)for a,b in zip(observed,source_heading))>1e-6:raise ValueError('Observed user heading differs from bound source')
  grade,curvature,reason=profile_at(road,binding.get('station_m'),native,observed)
  if grade is not None:user['road_grade']=grade
  if curvature is not None:user['road_curvature']=curvature
  diagnostics.append({'track':user['track'],'roadway_id':ident,'native_road_id':binding.get('native_road_id'),'station_m':binding.get('station_m'),'grade':grade,'curvature':curvature,'reason':reason})
 return diagnostics


def prepare_profile_source(path,roadway_sources):
 """Compile existing Native Driving geometry once; no observer or simulator."""
 if path is None:return {'roads':{},'lanes':[],'roadway_sources':{},'missing_source':'missing_original_road_map'}
 from .geometry import static_map
 from shapely.geometry import Polygon
 source={};native,_,_=static_map(path,include_non_driving=True,source_regions=source)
 lanes=[]
 for region in native:
  original=source.get(region['id'],{})
  if region['kind']=='lane'and original.get('road_id')is not None and region.get('boundary'):
   lanes.append((original['road_id'],Polygon(region['boundary'])))
 return {'roads':compile_profiles(path),'lanes':lanes,'roadway_sources':roadway_sources}

def _station(road,point):
 candidates=[]
 for g in road.findall('./planView/geometry'):
  start=float(g.get('s'));length=float(g.get('length'));h=float(g.get('hdg'));x=float(g.get('x'));y=float(g.get('y'));arc=g.find('arc');dx=point[0]-x;dy=point[1]-y
  if g.find('line')is not None:local=dx*math.cos(h)+dy*math.sin(h)
  elif arc is not None:
   k=float(arc.get('curvature'))
   if not k or abs(k*length)>=2*math.pi:return None
   cx=x-math.sin(h)/k;cy=y+math.cos(h)/k
   theta=math.atan2(k*(point[0]-cx),-k*(point[1]-cy));angle=(theta-h+math.pi)%(2*math.pi)-math.pi
   if k>0 and angle<0:angle+=2*math.pi
   if k<0 and angle>0:angle-=2*math.pi
   local=angle/k
  else:continue
  if -1e-6<=local<=length+1e-6:candidates.append(start+max(0.,min(length,local)))
 unique=[]
 for station in candidates:
  if not any(abs(station-old)<=1e-6 for old in unique):unique.append(station)
 return unique[0]if len(unique)==1 else None

def source_user_bindings(scene,source):
 """Unique original physical Roadway AND Native source surface, never nearest."""
 from shapely.geometry import Point,Polygon
 result={}
 for user in scene.get('users',[]):
  pos=user.get('kin',{}).get('position')
  if not isinstance(pos,list)or len(pos)!=2 or not all(finite(v)for v in pos):continue
  point=Point(pos);regions=[r for r in scene.get('structures',[])if r['kind']in('roadway','one_way_roadway')and r['id']in source['roadway_sources']and r.get('boundary')and Polygon(r['boundary']).covers(point)]
  if len(regions)!=1:continue
  region=regions[0];allowed=source['roadway_sources'][region['id']]
  native_ids={rid for rid,shape in source['lanes']if rid in allowed and shape.covers(point)}
  if len(native_ids)!=1:continue
  rid=next(iter(native_ids));native=[pos[0],-pos[1]];station=_station(source['roads'][rid],pos)
  if station is None:continue
  result[user['track']]={'roadway_id':region['id'],'unique_Roadway_candidates':[region['id']],
    'native_road_id':rid,'station_m':station,'position_native_m':native}
 return result

def project_source_profiles(scene,source):
 rows=project_user_profiles(scene,source['roads'],source_user_bindings(scene,source))
 if source.get('missing_source'):
  for row in rows:row['reason']=source['missing_source']
 return rows
