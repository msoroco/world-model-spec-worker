"""Measure source-bound rotary body passage without a legal verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path

FILES=('native-observed.jsonl','island-readback.json','island-frames.jsonl')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines()]


def finite(value):return type(value) in (int,float) and math.isfinite(value)


def measure(folder,expected_hashes=None):
    folder=Path(folder)
    hashes={name:sha(folder/name) for name in FILES}
    if expected_hashes is not None and hashes!=expected_hashes:
        raise ValueError('Rotary saved source hashes differ')
    observed=rows(folder/'native-observed.jsonl')
    frames=rows(folder/'island-frames.jsonl')
    island=json.loads((folder/'island-readback.json').read_text())
    if len(observed)!=240 or len(frames)!=240:
        raise ValueError('Rotary saved frame coverage differs')
    kind=observed[0].get('source_kind')
    case=observed[0].get('case')
    if (kind not in ('synthetic_cpu','original_native') or
            case not in ('reference','contrast') or
            island.get('source_kind')!=kind or
            island.get('center_xy_m')!=[0,0] or
            island.get('island_radius_m')!=15 or
            island.get('driving_lane_ids')!=[-2,-1] or
            island.get('physical_island_verified') is not False or
            island.get('traffic_control_verified') is not False or
            not isinstance(island.get('road_sha256'),str) or
            len(island['road_sha256'])!=64):
        raise ValueError('Rotary saved island/map readback differs')
    if kind=='original_native' and (not island.get('native_map_sha256') or
                                   island.get('review_provenance')!='human_frame_review'):
        raise ValueError('Original rotary map or frame-review source absent')
    direction=1 if case=='reference' else -1
    first_native=observed[0].get('native_frame')
    if type(first_native) is not int:
        raise ValueError('Rotary initial Native frame differs')
    previous_angle=None;angular_progress=0.0
    side_counts={'left':0,'right':0,'ambiguous':0}
    visible=0;entry_visible=0;min_clearance=float('inf');max_lane_offset=0.0
    for i,(row,frame) in enumerate(zip(observed,frames)):
        if (row.get('frame')!=i or frame.get('frame')!=i or
                row.get('native_frame')!=first_native+i or
                frame.get('native_frame')!=row['native_frame'] or
                row.get('case')!=case or row.get('source_kind')!=kind or
                frame.get('source_kind')!=kind or
                not finite(row.get('time_s')) or abs(row['time_s']-(i+1)/20)>1e-6 or
                not finite(frame.get('time_s')) or abs(frame['time_s']-row['time_s'])>1e-6 or
                frame.get('camera_frame')!=row['native_frame'] or
                type(frame.get('island_visible')) is not bool or
                row.get('lane_id') not in (-2,-1) or
                any(not finite(row.get(key)) for key in
                    ('ego_x_m','ego_y_m','ego_heading_deg','ego_speed_mps')) or
                row['ego_speed_mps']<0):
            raise ValueError('Rotary saved frame, lane or observation differs')
        if kind=='original_native' and (not row.get('ego_actor_id') or
                                        row.get('ego_blueprint')!='vehicle.tesla.model3'):
            raise ValueError('Original rotary ego identity differs')
        body=row.get('ego_body_xy_m')
        if (not isinstance(body,list) or len(body)<4 or
                any(not isinstance(point,list) or len(point)!=2 or
                    not all(finite(value) for value in point) for point in body)):
            raise ValueError('Rotary body vertices absent')
        x,y=row['ego_x_m'],row['ego_y_m']
        radius=math.hypot(x,y)
        expected_radius=27.25 if row['lane_id']==-2 else 23.75
        deviation=abs(radius-expected_radius)
        if deviation>.5:
            raise ValueError('Rotary body center outside claimed lane')
        max_lane_offset=max(max_lane_offset,deviation)
        angle=math.atan2(y,x)
        if previous_angle is not None:
            step=math.atan2(math.sin(angle-previous_angle),
                            math.cos(angle-previous_angle))
            if (direction*step<-.002 or
                    abs(abs(step)*radius*20-row['ego_speed_mps'])>.35):
                raise ValueError('Rotary motion, speed or passage direction differs')
            angular_progress+=step
        previous_angle=angle
        heading=math.radians(row['ego_heading_deg'])
        cross=math.cos(heading)*(-y)-math.sin(heading)*(-x)
        side='left' if cross>1 else 'right' if cross< -1 else 'ambiguous'
        side_counts[side]+=1
        for point in body:
            if math.hypot(point[0]-x,point[1]-y)>3.5:
                raise ValueError('Rotary body vertex detached from ego center')
            clearance=math.hypot(*point)-15
            min_clearance=min(min_clearance,clearance)
        if frame['island_visible']:
            visible+=1
            if i<40:entry_visible+=1
    passage=abs(angular_progress)>=math.pi
    return {'format':'c234827-saved-rotary-measurement-v1',
        'case':case,'source_kind':kind,'source_hashes':hashes,
        'frames':240,'angular_progress_rad':round(angular_progress,4),
        'half_circle_passage_observed':passage,
        'island_side_frame_counts':side_counts,
        'continuous_requested_side':side_counts['left' if direction==1 else 'right']==240,
        'minimum_body_island_clearance_m':round(min_clearance,3),
        'maximum_lane_center_deviation_m':round(max_lane_offset,3),
        'island_visible_frames':visible,
        'entry_visible_frames':entry_visible,
        'physical_island_verified':False,'traffic_control_verified':False,
        'legal_verdict':None,'delivery_ready':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path)
    args=parser.parse_args();print(json.dumps(measure(args.folder),indent=2))
