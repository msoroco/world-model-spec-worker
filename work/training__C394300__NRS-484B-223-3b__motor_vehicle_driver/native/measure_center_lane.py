"""Measure entry-to-left-turn distance from saved Native body/pose samples.

An authored center-lane polygon is not proof of its Native legal designation.
The distance interval brackets two events between sampled frames; it does not
assign a legal outcome at a boundary it cannot resolve.
"""
import hashlib
import json
import math
from pathlib import Path

THRESHOLD_M=200*0.3048


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def point(value,name):
    if not isinstance(value,(list,tuple)) or len(value)!=2:
        raise ValueError('Invalid Native point: '+name)
    result=tuple(float(x) for x in value)
    if not all(math.isfinite(x) for x in result):raise ValueError('Nonfinite Native point: '+name)
    return result


def inside(vertex,bounds):
    x,y=vertex
    return bounds[0]<=x<=bounds[2] and bounds[1]<=y<=bounds[3]


def segment_intersects_box(a,b,bounds):
    if inside(a,bounds) or inside(b,bounds):return True
    # Liang-Barsky clipping of the original body edge against the lane box.
    dx=b[0]-a[0];dy=b[1]-a[1];lo=0.0;hi=1.0
    for p,q in ((-dx,a[0]-bounds[0]),(dx,bounds[2]-a[0]),
                (-dy,a[1]-bounds[1]),(dy,bounds[3]-a[1])):
        if abs(p)<1e-12:
            if q<0:return False
        else:
            t=q/p
            if p<0:lo=max(lo,t)
            else:hi=min(hi,t)
            if lo>hi:return False
    return True


def overlaps(vertices,bounds):
    if any(inside(v,bounds) for v in vertices):return True
    corners=[(bounds[0],bounds[1]),(bounds[0],bounds[3]),
             (bounds[2],bounds[3]),(bounds[2],bounds[1])]
    def body_contains(p):
        crosses=[(vertices[(i+1)%4][0]-vertices[i][0])*(p[1]-vertices[i][1])-
                 (vertices[(i+1)%4][1]-vertices[i][1])*(p[0]-vertices[i][0])
                 for i in range(4)]
        return all(v>=-1e-9 for v in crosses) or all(v<=1e-9 for v in crosses)
    if any(body_contains(corner) for corner in corners):return True
    return any(segment_intersects_box(vertices[i],vertices[(i+1)%4],bounds) for i in range(4))


def measure(samples_path,geometry_path):
    samples_path=Path(samples_path);geometry_path=Path(geometry_path)
    for path in (samples_path,geometry_path):
        if not path.is_file():raise ValueError('Missing required source: '+path.name)
    geometry=json.loads(geometry_path.read_text())
    bounds=geometry.get('center_turn_lane_native_xy_bounds_m')
    if not isinstance(bounds,list) or len(bounds)!=4 or not all(math.isfinite(float(v)) for v in bounds):
        raise ValueError('Missing finite center-lane Native bounds')
    bounds=list(map(float,bounds))
    if not bounds[0]<bounds[2] or not bounds[1]<bounds[3]:raise ValueError('Invalid center-lane bounds')
    lane_id=geometry.get('center_turn_lane_native_id')
    if not isinstance(lane_id,int):raise ValueError('Missing center-lane Native ID')
    direction=point(geometry.get('approach_forward_native_xy'),'approach_forward_native_xy')
    norm=math.hypot(*direction)
    if abs(norm-1)>.01:raise ValueError('Approach direction is not unit length')
    rows=[json.loads(line) for line in samples_path.read_text().splitlines() if line.strip()]
    if len(rows)<4:raise ValueError('Too few Native samples')
    cumulative=[];last_frame=-math.inf;last_time=-math.inf;last_center=None
    contact=[];full=[];turn=[]
    for i,row in enumerate(rows):
        frame=row.get('native_frame');time=float(row['time_s'])
        if not isinstance(frame,int) or frame<=last_frame or not math.isfinite(time) or time<=last_time:
            raise ValueError('Native frame/time order invalid')
        last_frame=frame;last_time=time
        center=point(row.get('native_center_xy_m'),'native_center_xy_m')
        vertices=[point(v,'native_body_xy_m') for v in row.get('native_body_xy_m',[])]
        if len(vertices)!=4:raise ValueError('Original full Native body missing')
        heading=point(row.get('native_forward_xy'),'native_forward_xy')
        if abs(math.hypot(*heading)-1)>.01:raise ValueError('Native heading is not unit length')
        cumulative.append((cumulative[-1] if cumulative else 0.0)+
                          (math.dist(last_center,center) if last_center else 0.0))
        last_center=center
        contact.append(overlaps(vertices,bounds))
        full.append(all(inside(v,bounds) for v in vertices) and row.get('native_lane_id')==lane_id)
        cross=direction[0]*heading[1]-direction[1]*heading[0]
        dot=direction[0]*heading[0]+direction[1]*heading[1]
        turn.append(math.degrees(math.atan2(cross,dot))>=5.0)
    entry=next((i for i,v in enumerate(contact) if v),None)
    if entry is None or entry==0 or contact[0]:raise ValueError('Center-lane entry lacks a preceding outside sample')
    turn_index=next((i for i,v in enumerate(turn) if v),None)
    if turn_index is None or turn_index<=entry+1:raise ValueError('Observed left-turn onset absent after lane entry')
    if not any(full[entry:turn_index]) or not all(full[i] for i in range(entry+1,turn_index)):
        raise ValueError('Continuous sampled center-lane occupancy absent before turn')
    if not all(rows[i]['native_lane_id']==lane_id for i in range(entry+1,turn_index+1)):
        raise ValueError('Native lane identity changed before turn')
    lower=max(0,cumulative[turn_index-1]-cumulative[entry])
    upper=cumulative[turn_index]-cumulative[entry-1]
    side='within_200_feet' if upper<THRESHOLD_M else 'exceeds_200_feet' if lower>THRESHOLD_M else 'unresolved_at_200_feet'
    return {'format':'center-turn-lane-entry-to-left-turn-measurement-v1',
      'threshold_m':THRESHOLD_M,'threshold_source':'NRS 484B.223(3)(b): 200 feet',
      'entry_frame_bracket':[rows[entry-1]['native_frame'],rows[entry]['native_frame']],
      'turn_onset_frame_bracket':[rows[turn_index-1]['native_frame'],rows[turn_index]['native_frame']],
      'entry_to_turn_distance_interval_m':[lower,upper],
      'sampled_distance_m':cumulative[turn_index]-cumulative[entry],
      'threshold_relation':side,
      'native_center_lane_design_verified':geometry.get('native_center_lane_design_verified') is True,
      'source_hashes':{samples_path.name:sha(samples_path),geometry_path.name:sha(geometry_path)},
      'limitations':['Sample brackets do not locate continuous entry or turn onset exactly',
                     'Center-lane Native designation and legal outcome require independent evidence']}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--samples',required=True)
    parser.add_argument('--geometry',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();Path(args.output).write_text(json.dumps(measure(args.samples,args.geometry),indent=2)+'\n')
