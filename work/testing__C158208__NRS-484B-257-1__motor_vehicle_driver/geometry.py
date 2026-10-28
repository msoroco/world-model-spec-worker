"""Offline physical geometry checks; CARLA y is opposite authored OpenDRIVE y."""
import math,xml.etree.ElementTree as ET

def elevation(nodes,s):
 selected=[n for n in nodes if float(n.attrib['s'])<=s]
 if not selected:return 0.
 n=selected[-1];d=s-float(n.attrib['s'])
 return sum(float(n.attrib.get(k,0))*d**i for i,k in enumerate('abcd'))

def rectangle(position,yaw,half_length,half_width):
 c,s=math.cos(yaw),math.sin(yaw)
 return [[position[0]+c*x-s*y,position[1]+s*x+c*y] for x,y in [(-half_length,-half_width),(half_length,-half_width),(half_length,half_width),(-half_length,half_width)]]

def overlaps(a,b):
 """Convex SAT with contact retained as contact; downstream chooses legal convention."""
 for poly in (a,b):
  for i,p in enumerate(poly):
   q=poly[(i+1)%len(poly)];axis=(-(q[1]-p[1]),q[0]-p[0])
   aa=[x*axis[0]+y*axis[1] for x,y in a];bb=[x*axis[0]+y*axis[1] for x,y in b]
   if max(aa)<min(bb) or max(bb)<min(aa):return False
 return True

def validate_map(path,mechanism,search_distance=230.):
 root=ET.parse(path).getroot();roads={int(r.attrib['id']):r for r in root.findall('road')}
 assert len(roads)==len(root.findall('road'))
 for r in roads.values():
  geoms=r.findall('./planView/geometry');length=float(r.attrib['length'])
  assert geoms and abs(sum(float(g.attrib['length']) for g in geoms)-length)<1e-6
  assert all(float(l.find('width').attrib['a'])>0 for l in r.findall('./lanes/laneSection/right/lane'))
 if mechanism in ('yield','reverse'):
  # Native topology links: the two crossing movements have actual junction connectors.
  assert roads[11].attrib['junction']=='0' and roads[21].attrib['junction']=='0'
  for cid in (11,21):
   r=roads[cid]
   for tag in ('predecessor','successor'):
    link=r.find('./link/'+tag);assert int(link.attrib['elementId']) in roads
  assert len(root.findall('./junction/connection'))==3
 if mechanism=='uturn':
  # Both incoming directions must extend past the complete planned maneuver envelope.
  start,end=350.,500.
  assert start-search_distance>0 and end+search_distance<float(roads[1].attrib['length'])
  z=roads[1].findall('./elevationProfile/elevation')
  assert elevation(z,500)>elevation(z,300) and elevation(z,500)>elevation(z,700)
 return {'authored_geometry_validated':True,'native_import_and_ray_coverage_confirmed':False}

def validate_uturn_footprint(station,half_length=2.8,half_width=1.25):
 # With centre (station+6sin(t),6cos(t)), heading -t, every corner has
 # y=(6+corner_y)cos(t)-corner_x sin(t). The analytic amplitude bounds all t.
 lateral_bound=math.hypot(6+half_width,half_length)
 if lateral_bound>=12:raise ValueError('Full U-turn swept body exceeds native 24m operating surface')
 longitudinal_bound=lateral_bound
 if station-longitudinal_bound<=0 or station+longitudinal_bound>=1800:raise ValueError('Full U-turn body exceeds authored road ends')
 for i in range(721):
  t=i*math.pi/720;p=(station+6*math.sin(t),6*math.cos(t))
  for corner in rectangle(p,-t,half_length,half_width):
   if not 0<corner[0]<1800 or not -12<corner[1]<12:raise ValueError('Intermediate U-turn footprint outside native road')
 return {'continuous_lateral_amplitude_bound_m':lateral_bound,'half_length_limit_m':half_length,'half_width_limit_m':half_width,'sampled_whole_semicircle_poses':721,'native_physics_clearance_confirmed':False}
