"""Build a continuous synthetic opposite turn for CPU proof rehearsal."""
import copy
import hashlib
import json
import math
from pathlib import Path
from shapely.geometry import MultiPoint, Polygon

P = Path('work/testing__C125751__NRS-484B-250-2__motor_vehicle_driver')
OUT = P / 'opposite-turn-v2-sources'
OUT.mkdir(exist_ok=True)
(OUT / 'capture').mkdir(exist_ok=True)

def rows(name):
    return [json.loads(line) for line in (P / 'straight-diagnostic-sources' / name).read_text().splitlines()]

def dump(path, data):
    path.write_text(''.join(json.dumps(x, separators=(',', ':')) + '\n' for x in data))

def pose(i):
    if i <= 70:
        return (-8., 0., 0.)
    if i <= 96:
        return (-8. + (i-70)*.25, 0., 0.)
    if i <= 106:
        a = -math.pi/2 + (i-96)*math.pi/20
        return (-1.5 + 1.5*math.cos(a), 1.5 + 1.5*math.sin(a), math.degrees(a+math.pi/2))
    if i <= 140:
        return (0., 1.5 + (i-106)*.25, 90.)
    return (0., 10., 90.)

def body(i):
    x,y,h = pose(i)
    a=math.radians(h)
    verts=[]
    for fore,side in ((-2,-1),(-2,1),(2,-1),(2,1)):
        verts.append([round(x+fore*math.cos(a)-side*math.sin(a), 6),
                      round(y+fore*math.sin(a)+side*math.cos(a), 6)])
    x0,y0,_=pose(max(0,i-1));vx=round((x-x0)*20,6);vy=round((y-y0)*20,6)
    speed=math.hypot(vx,vy)
    return dict(heading_deg=round(h,6),native_road_id=1,native_lane_id=-1,
                velocity_xyz_mps=[vx,vy,0.],speed_mps=speed,body_vertices_xy_m=verts)

def verts3(v):
    return [[x,y,z] for x,y in v for z in (0.,1.5)]

def inside(v):
    return MultiPoint(v).convex_hull.intersects(Polygon([(-2,-2),(2,-2),(2,2),(-2,2)]))

bodies=rows('body_history.jsonl'); crossings=rows('crossing_history.jsonl')
stops=rows('stop_history.jsonl'); captures=rows('capture/evidence.jsonl')
spec=json.loads((P/'opposite-diagnostic-fixture-spec.json').read_text())
traces=[json.loads(z) for z in spec['files']['trace.jsonl'].splitlines()]
for i,(b,c,s,e,t,g) in enumerate(zip(bodies,crossings,stops,captures,traces,spec['graphs'])):
    ego=body(i);x,y,h=pose(i);v3=verts3(ego['body_vertices_xy_m'])
    b.pop('maneuver',None);b['turning_role']='ego';b['actor_sources']['ego']=ego
    c['ego']=copy.deepcopy(ego);c['other']=copy.deepcopy(b['actor_sources']['other']);c['ego_vertices_m']=copy.deepcopy(ego['body_vertices_xy_m'])
    for role in ('ego','other'):
        act=b['actor_sources'][role];v=act['body_vertices_xy_m']
        heading=math.radians(act['heading_deg']);front=max(v,key=lambda q:q[0]*math.cos(heading)+q[1]*math.sin(heading))
        s[role]=dict(speed_mps=act['speed_mps'],front_xy_m=front,body_inside_crossing=inside(v),native_road_id=act['native_road_id'],native_lane_id=act['native_lane_id'])
    participants=e['original_observations']['participants']
    for role,part in zip(('ego','other'),participants):
        act=b['actor_sources'][role]; vv=act['body_vertices_xy_m']
        if role=='ego':cx,cy=x,y
        else:cx=sum(q[0] for q in vv)/4;cy=sum(q[1] for q in vv)/4
        part.update(position_m=[cx,cy,0.],heading_deg=act['heading_deg'],speed_mps=act['speed_mps'],velocity_mps=act['velocity_xyz_mps'],body_vertices_m=verts3(vv))
    e['ego'].update(position_m=[x,y,0.],heading_deg=h,speed_mps=ego['speed_mps'],body_vertices_m=v3)
    g['attributes']['observed_evidence']=copy.deepcopy(e['original_observations'])
    t.update(position={'x':x,'y':y,'z':0.},position_m=[x,y,0.],heading_deg=h,speed_mps=ego['speed_mps'],speed_mph=ego['speed_mps']*2.2369362920544025,velocity_mps=ego['velocity_xyz_mps'])

for name,data in [('body_history.jsonl',bodies),('crossing_history.jsonl',crossings),('stop_history.jsonl',stops),('capture/evidence.jsonl',captures)]:
    dump(OUT/name,data)
spec['files']['trace.jsonl']=''.join(json.dumps(x,separators=(',',':'))+'\n' for x in traces)
manifest=json.loads(spec['files']['capture/manifest.json'])
manifest['sources']['trace.jsonl']=hashlib.sha256(spec['files']['trace.jsonl'].encode()).hexdigest()
spec['files']['capture/manifest.json']=json.dumps(manifest,indent=2)+'\n'
spec_path=P/'opposite-turn-v2-fixture-spec.json';spec_path.write_text(json.dumps(spec,separators=(',',':'))+'\n')
recipe=json.loads((P/'opposite-diagnostic-recipe.json').read_text())
recipe['generator']={'source':str(spec_path),'sha256':hashlib.sha256(spec_path.read_bytes()).hexdigest()}
for item in recipe['sources']:
    if item['source'].startswith('work/'):
        src=OUT / item['path'];item['source']=str(src);item['sha256']=hashlib.sha256(src.read_bytes()).hexdigest()
(P/'opposite-turn-v2-recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
print(json.dumps({'sources':{item['path']:item['sha256'] for item in recipe['sources']},'generator':recipe['generator']['sha256'],'end_ego':pose(1099)},indent=2))
