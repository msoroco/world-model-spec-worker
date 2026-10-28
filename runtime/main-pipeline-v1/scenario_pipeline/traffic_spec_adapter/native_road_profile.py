"""Source-bound generated straight-road grade patches and physical crest ridge.

The ridge's narrow strip is a mesh-resolution representation of a maximum,
never a statutory near-crest extent. Grade is a midpoint derivative estimate;
its spatial error bound is retained outside Core, which has no uncertainty field.
Older captures without the original instrumentation packet remain unsupported.
"""
import hashlib,json,math,xml.etree.ElementTree as ET
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def derivative(e,s):
 d=s-float(e.attrib['s']);return float(e.attrib.get('b',0))+2*float(e.attrib.get('c',0))*d+3*float(e.attrib.get('d',0))*d*d

def apply(original,telemetry,regions,polygons):
 original=Path(original);path=original/'native_road_profile.json'
 if not path.exists():return None
 from shapely.geometry import Polygon
 from batch_pipeline.completion import verify
 result=json.loads((original/'result.json').read_text());verify(original,result['completion']['binding'])
 packet=json.loads(path.read_text());construction=json.loads((original/'construction.json').read_text());files={f['path']:f['content'] for f in construction['files']}
 if (packet.get('schema')!='native-straight-road-profile-v1' or packet['map_sha256']!=sha(original/'road.xodr') or packet['survey_sha256']!=sha(original/'native_hill_surface_survey.json') or packet['instrumentation_sha256']!=sha(original/'runner.py') or hashlib.sha256(files['runner.py'].encode()).hexdigest()!=sha(original/'runner.py')):raise ValueError('Native road profile provenance mismatch')
 root=ET.parse(original/'road.xodr').getroot();roads=root.findall('road')
 if len(roads)!=1 or len(roads[0].findall('./planView/geometry'))!=1:raise ValueError('Native profile requires one straight road')
 road=roads[0];g=road.find('./planView/geometry')
 if g.find('line') is None or any(abs(float(g.attrib.get(k,0)))>1e-9 for k in ('x','y','hdg')):raise ValueError('Unsupported native profile frame')
 elev=road.findall('./elevationProfile/elevation');survey=json.loads((original/'native_hill_surface_survey.json').read_text())
 if survey['native_map_sha256']!=packet['map_sha256']:raise ValueError('Survey differs from native map')
 width=packet['half_road_width_m'];spacing=packet['grade_patch_length_m'];ridge_width=packet['crest_ridge_mesh_width_m']
 if spacing!=2 or ridge_width!=.25 or width!=12:raise ValueError('Unsupported profile resolution')
 if {v['lane_id'] for v in survey['surface_samples']}!={-1,1} or {v['s_m'] for v in survey['surface_samples']}!=set(range(450,1051,10)):raise ValueError('Incomplete two-direction native profile survey')
 for v in survey['surface_samples']:
  s=v['s_m'];e=max((x for x in elev if float(x.attrib['s'])<=s),key=lambda x:float(x.attrib['s']));d=s-float(e.attrib['s']);z=sum(float(e.attrib.get(k,0))*d**i for i,k in enumerate('abcd'));p=v['native_waypoint_m'];hits=v['all_surface_hits'];pitch=(math.radians(v['native_rotation_deg']['pitch'])+math.pi)%(2*math.pi)-math.pi
  if abs(p[0]-s)>.03 or abs(abs(p[1])-6)>.03 or abs(p[2]-z)>.02 or abs(pitch-(1 if v['lane_id']==-1 else -1)*derivative(e,s))>.001:raise ValueError('Native waypoint contradicts profile')
  if not hits or max(h['position_m'][2] for h in hits)>z+.05 or not any(abs(h['position_m'][2]-z)<.05 for h in hits):raise ValueError('Native topmost surface contradicts profile')
 for t in telemetry:
  v=t.get('native_road_profile',{});s=v.get('s_m');z=v.get('native_z_before_after_m',[])
  if v.get('frame')!=t['frame'] or v.get('time_s')!=t['time_s'] or v.get('map_sha256')!=packet['map_sha256'] or not isinstance(s,(int,float)) or not 450<s<1050 or len(z)!=2:raise ValueError('Missing original per-frame profile observation')
  e=max((x for x in elev if float(x.attrib['s'])<=s),key=lambda x:float(x.attrib['s']))
  if abs((z[1]-z[0])/.5-derivative(e,s))>.0001:raise ValueError('Original native local surface slope contradicts profile')
 def region(kind,a,b,**fields):
  rid=max((r['id'] for r in regions),default=0)+1;boundary=[[a,-width],[b,-width],[b,width],[a,width]];regions.append(dict(id=rid,kind=kind,boundary=boundary,**fields));polygons[rid]=Polygon(boundary);return rid
 patches=[]
 for start in range(450,1050,2):
  middle=start+1;e=max((x for x in elev if float(x.attrib['s'])<=middle),key=lambda x:float(x.attrib['s']));d=middle-float(e.attrib['s']);slope=derivative(e,middle);error=abs(2*float(e.attrib.get('c',0))+6*float(e.attrib.get('d',0))*d)+3*abs(float(e.attrib.get('d',0)))
  patches.append({'region_id':region('roadway',start,start+2,grade=slope),'station_interval_m':[start,start+2],'midpoint_grade_ratio':slope,'maximum_spatial_grade_error_ratio':error})
 crests=[]
 for i,e in enumerate(elev):
  if float(e.attrib.get('d',0))!=0:raise ValueError('Cubic profile needs separate crest derivation')
  c=float(e.attrib.get('c',0));b=float(e.attrib.get('b',0));start=float(e.attrib['s']);end=float(elev[i+1].attrib['s']) if i+1<len(elev) else float(road.attrib['length'])
  if c<0:
   peak=start-b/(2*c)
   if start<peak<end:
    if not any(v['s_m']==peak and abs(derivative(e,peak))<1e-9 for v in survey['surface_samples']):raise ValueError('Physical crest lacks native peak survey')
    crests.append({'region_id':region('crest',peak-ridge_width/2,peak+ridge_width/2),'station_m':peak,'mesh_representation_width_m':ridge_width,'legal_near_extent':None})
 if not crests:raise ValueError('No surveyed physical crest')
 return {'source':str(path),'sha256':sha(path),'grade_patches':patches,'physical_crests':crests,'scope':'Native surveyed elevation geometry. Midpoint grades approximate local2m patches; narrow crest ridge represents physical maximum at mesh resolution. No statutory near extent, visibility or compliance judgment.'}
