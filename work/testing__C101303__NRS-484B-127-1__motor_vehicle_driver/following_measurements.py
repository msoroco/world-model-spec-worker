"""Original-frame following before a hill-crest lane change.

Reports complete-body geometry, both velocities, traffic and road condition.
Reasonable-and-prudent distance remains a legal judgment without a numeric cutoff.
"""
import hashlib
import json
import math
from pathlib import Path
from shapely.geometry import MultiPoint, Polygon

REQUIRED = ('road_context.json', 'vehicle_history.jsonl', 'video_frames.jsonl')

def number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Missing finite '+label)
    return float(value)

def vector(value, label, dimensions):
    if not isinstance(value, list) or len(value)!=dimensions:
        raise ValueError('Missing '+label)
    return tuple(number(v,label) for v in value)

def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def body(actor, label):
    values=actor.get('body_vertices_xy_m')
    if not isinstance(values,list) or len(values)<4:
        raise ValueError('Missing complete '+label+' body')
    polygon=MultiPoint([vector(v,label+' vertex',2) for v in values]).convex_hull
    if polygon.area<=0:raise ValueError('Degenerate '+label+' body')
    return polygon

def analyze(root:Path)->dict:
    root=Path(root);hashes={}
    for name in REQUIRED:
        path=root/name
        if not path.is_file():raise ValueError('Missing original source: '+name)
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    ctx=json.loads((root/'road_context.json').read_text())
    for key in ('native_map_id','highway_id','road_id','following_lane_id',
                'target_lane_id','hill_crest_source','lane_geometry_source',
                'surface_source','traffic_source','route_source'):
        if ctx.get(key) is None:raise ValueError('Missing sourced road context: '+key)
    if ctx['following_lane_id']==ctx['target_lane_id']:
        raise ValueError('Lane change target equals following lane')
    forward=vector(ctx.get('following_forward_xy'),'following direction',2)
    norm=math.hypot(*forward)
    if norm==0:raise ValueError('Zero following direction')
    fx,fy=forward[0]/norm,forward[1]/norm
    lx,ly=-fy,fx
    original,frames=rows(root/'vehicle_history.jsonl'),rows(root/'video_frames.jsonl')
    if len(original)<3 or len(original)!=len(frames):raise ValueError('Incomplete following/frame history')
    previous=(-1,-math.inf);samples=[];first_change=None
    for i,(row,frame) in enumerate(zip(original,frames)):
        fid,time=row.get('frame'),number(row.get('time_s'),'time')
        if type(fid) is not int or fid<=previous[0] or time<=previous[1]:
            raise ValueError('Nonmonotone original history')
        previous=fid,time
        if frame.get('video_frame')!=i or frame.get('carla_frame')!=fid or frame.get('time_s')!=time:
            raise ValueError('Original frame join failed')
        if row.get('road_id')!=ctx['road_id']:
            raise ValueError('Ego on wrong road')
        ego,lead=row.get('ego'),row.get('lead')
        if not isinstance(ego,dict) or not isinstance(lead,dict):raise ValueError('Missing both vehicle sources')
        if ego.get('actor_id')==lead.get('actor_id') or not ego.get('actor_id') or not lead.get('actor_id'):
            raise ValueError('Distinct Native vehicle identities required')
        eb,lb=body(ego,'ego'),body(lead,'lead')
        ev=vector(ego.get('velocity_mps'),'ego velocity',3)
        lv=vector(lead.get('velocity_mps'),'lead velocity',3)
        if ego.get('speed_source')!='actor.get_velocity' or lead.get('speed_source')!='actor.get_velocity':
            raise ValueError('Original Native velocities required')
        if ego.get('lane_id') not in (ctx['following_lane_id'],ctx['target_lane_id']):
            raise ValueError('Unexpected ego lane')
        if lead.get('lane_id')!=ctx['following_lane_id']:
            raise ValueError('Lead left sourced following lane')
        if row.get('surface_condition') not in ('dry','wet','snow','ice','other_sourced'):
            raise ValueError('Road condition missing')
        traffic=row.get('traffic_actor_ids')
        if not isinstance(traffic,list) or not all(type(a) is int for a in traffic):
            raise ValueError('Traffic inventory missing')
        if ego['actor_id'] not in traffic or lead['actor_id'] not in traffic:
            raise ValueError('Subject and lead absent from traffic inventory')
        ego_long=[x*fx+y*fy for x,y in eb.exterior.coords]
        lead_long=[x*fx+y*fy for x,y in lb.exterior.coords]
        ego_lat=[x*lx+y*ly for x,y in eb.exterior.coords]
        lead_lat=[x*lx+y*ly for x,y in lb.exterior.coords]
        longitudinal_gap=min(lead_long)-max(ego_long)
        lateral_overlap=min(max(ego_lat),max(lead_lat))-max(min(ego_lat),min(lead_lat))
        same_lane=ego['lane_id']==ctx['following_lane_id']
        following=same_lane and longitudinal_gap>0 and lateral_overlap>0
        change=row.get('lane_change_started')
        if type(change) is not bool:raise ValueError('Lane-change event missing')
        if change and first_change is None:first_change={'frame':fid,'time_s':time}
        if first_change and not change:raise ValueError('Lane-change event regressed')
        samples.append({'frame':fid,'time_s':time,'ego_lane_id':ego['lane_id'],
                        'lead_lane_id':lead['lane_id'],'following':following,
                        'longitudinal_body_gap_m':longitudinal_gap,
                        'lateral_body_overlap_m':lateral_overlap,
                        'ego_speed_mps':math.sqrt(sum(v*v for v in ev)),
                        'lead_speed_mps':math.sqrt(sum(v*v for v in lv)),
                        'lead_brake':bool(lead.get('brake_applied')),
                        'surface_condition':row['surface_condition'],
                        'traffic_actor_ids':traffic,'lane_change_started':change})
    if first_change is None:raise ValueError('No observed lane change')
    before=[s for s in samples if s['time_s']<first_change['time_s']]
    if not before or not any(s['following'] for s in before):
        raise ValueError('No observed following before lane change')
    during=[s for s in samples if s['following']]
    return {'format':'worker-hill-crest-following-observations','sources':hashes,
            'first_lane_change':first_change,'following_start':{'frame':during[0]['frame'],'time_s':during[0]['time_s']},
            'following_end':{'frame':during[-1]['frame'],'time_s':during[-1]['time_s']},
            'following_overlaps_lane_change':any(s['time_s']>=first_change['time_s'] for s in during),
            'minimum_sampled_body_gap_m':min(s['longitudinal_body_gap_m'] for s in before if s['following']),
            'samples':samples,'reasonable_and_prudent_judgment':'unresolved; no statutory numeric gap',
            'legal_conclusion':'unresolved'}
