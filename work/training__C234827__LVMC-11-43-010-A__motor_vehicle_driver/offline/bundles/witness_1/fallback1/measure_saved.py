"""Measure source-bound roundabout occupancy and per-frame rotation."""
import argparse
import hashlib
import json
import math
from pathlib import Path

FILES=('native-observed.jsonl','roundabout-readback.json','roundabout-frames.jsonl')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines()]
def finite(value):return type(value) in (int,float) and math.isfinite(value)


def measure(folder,expected_hashes=None):
    folder=Path(folder)
    hashes={name:sha(folder/name) for name in FILES}
    if expected_hashes is not None and hashes!=expected_hashes:
        raise ValueError('Roundabout saved source hashes differ')
    observed=rows(folder/'native-observed.jsonl')
    frames=rows(folder/'roundabout-frames.jsonl')
    readback=json.loads((folder/'roundabout-readback.json').read_text())
    if len(observed)!=240 or len(frames)!=240:
        raise ValueError('Roundabout saved frame coverage differs')
    kind=observed[0].get('source_kind')
    witness=observed[0].get('witness')
    if (kind not in ('synthetic_cpu','original_native') or
            witness not in ('witness_1','witness_2') or
            readback.get('source_kind')!=kind or
            readback.get('center_xy_m')!=[0,0] or
            readback.get('island_radius_m')!=15 or
            readback.get('driving_lane_ids')!=[-2,-1] or
            readback.get('roundabout_verified') is not False or
            readback.get('traffic_control_verified') is not False or
            not isinstance(readback.get('road_sha256'),str) or
            len(readback['road_sha256'])!=64):
        raise ValueError('Roundabout saved map/readback differs')
    if kind=='original_native' and (not readback.get('native_map_sha256') or
                                   readback.get('review_provenance')!='human_frame_review'):
        raise ValueError('Original roundabout map or frame review absent')
    first_native=observed[0].get('native_frame')
    if type(first_native) is not int:
        raise ValueError('Roundabout initial Native frame differs')
    previous_angle=None;progress=0.0;max_lane_deviation=0.0
    ccw=0;cw=0;ambiguous=0;occupied=0;visible=0;entry_visible=0
    min_body_clearance=float('inf');max_yaw_rate=0.0
    previous_heading=None
    for i,(row,frame) in enumerate(zip(observed,frames)):
        if (row.get('frame')!=i or frame.get('frame')!=i or
                row.get('native_frame')!=first_native+i or
                frame.get('native_frame')!=row['native_frame'] or
                row.get('witness')!=witness or row.get('source_kind')!=kind or
                frame.get('source_kind')!=kind or
                not finite(row.get('time_s')) or abs(row['time_s']-(i+1)/20)>1e-6 or
                not finite(frame.get('time_s')) or abs(frame['time_s']-row['time_s'])>1e-6 or
                frame.get('camera_frame')!=row['native_frame'] or
                type(frame.get('roundabout_visible')) is not bool or
                row.get('lane_id') not in (-2,-1) or
                any(not finite(row.get(key)) for key in
                    ('ego_x_m','ego_y_m','ego_heading_deg','ego_speed_mps')) or
                row['ego_speed_mps']<0):
            raise ValueError('Roundabout saved frame or observation differs')
        if kind=='original_native' and (not row.get('ego_actor_id') or
                                        row.get('ego_blueprint')!='vehicle.tesla.model3'):
            raise ValueError('Original roundabout ego identity differs')
        body=row.get('ego_body_xy_m')
        if (not isinstance(body,list) or len(body)<4 or
                any(not isinstance(point,list) or len(point)!=2 or
                    not all(finite(value) for value in point) for point in body)):
            raise ValueError('Roundabout body vertices absent')
        x,y=row['ego_x_m'],row['ego_y_m']
        radius=math.hypot(x,y)
        expected_radius=27.25 if row['lane_id']==-2 else 23.75
        deviation=abs(radius-expected_radius)
        if deviation>.5:raise ValueError('Roundabout ego outside claimed lane')
        max_lane_deviation=max(max_lane_deviation,deviation)
        heading=math.radians(row['ego_heading_deg'])
        cross=x*math.sin(heading)-y*math.cos(heading)
        if cross>1:ccw+=1
        elif cross< -1:cw+=1
        else:ambiguous+=1
        theta=math.atan2(y,x)
        if previous_angle is not None:
            step=math.atan2(math.sin(theta-previous_angle),
                            math.cos(theta-previous_angle))
            if abs(abs(step)*radius*20-row['ego_speed_mps'])>.35:
                raise ValueError('Roundabout motion/speed differs')
            if (step>0 and cross< -1) or (step<0 and cross>1):
                raise ValueError('Roundabout pose/heading direction differs')
            progress+=step
            yaw=math.atan2(math.sin(heading-previous_heading),
                           math.cos(heading-previous_heading))*20
            max_yaw_rate=max(max_yaw_rate,abs(yaw))
            if abs(yaw-step*20)>.15:
                raise ValueError('Roundabout yaw rate and path direction differ')
        previous_angle=theta;previous_heading=heading
        for point in body:
            if math.hypot(point[0]-x,point[1]-y)>3.5:
                raise ValueError('Roundabout body vertex detached')
            min_body_clearance=min(min_body_clearance,math.hypot(*point)-15)
        if min_body_clearance>0 and 20<=radius<=29:occupied+=1
        if frame['roundabout_visible']:
            visible+=1
            if i<40:entry_visible+=1
    return {'format':'c234827-lvmc-saved-rotation-v1',
        'witness':witness,'source_kind':kind,'source_hashes':hashes,
        'frames':240,'signed_angular_progress_rad':round(progress,4),
        'half_circle_passage_observed':abs(progress)>=math.pi,
        'rotation_frame_counts':{'counterclockwise':ccw,'clockwise':cw,
                                 'ambiguous':ambiguous},
        'continuous_requested_rotation':
            (ccw==240 if witness=='witness_1' else cw==240),
        'occupied_authored_ring_frames':occupied,
        'minimum_body_island_clearance_m':round(min_body_clearance,3),
        'maximum_lane_center_deviation_m':round(max_lane_deviation,3),
        'maximum_abs_yaw_rate_radps':round(max_yaw_rate,4),
        'roundabout_visible_frames':visible,'entry_visible_frames':entry_visible,
        'roundabout_verified':False,'traffic_control_verified':False,
        'legal_verdict':None,'delivery_ready':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path)
    args=parser.parse_args();print(json.dumps(measure(args.folder),indent=2))
