"""Source-bound fallback decisions for the turn/straight controlled pair."""
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def point(value):
    if not isinstance(value,list) or len(value)!=2 or any(
            type(v) not in (int,float) or not math.isfinite(v) for v in value):
        raise ValueError('Invalid Native or requested route point')
    return value


def distance(p,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    length2=dx*dx+dy*dy
    if length2==0:raise ValueError('Degenerate requested route segment')
    t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/length2))
    return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)


def evaluate(samples_path,geometry_path,map_audit_path,pixel_audit_path,video_path,
             requested_route_xy_m,requested_movement):
    """Evaluate three distinct triggers from an original-attempt source packet.

    A synthetic packet tests the calculation, but cannot establish the claimed
    Native map readback or original-pixel provenance.
    """
    paths=[Path(p) for p in (samples_path,geometry_path,map_audit_path,pixel_audit_path,video_path)]
    if any(not p.is_file() for p in paths):raise ValueError('Missing trigger source')
    if requested_movement not in ('right_turn','straight_through'):
        raise ValueError('Unknown requested movement')
    samples=[json.loads(line) for line in paths[0].read_text().splitlines() if line.strip()]
    if len(samples)<4:raise ValueError('Too few original Native samples')
    geometry=json.loads(paths[1].read_text())
    mapping=json.loads(paths[2].read_text())
    pixels=json.loads(paths[3].read_text())
    if not isinstance(geometry.get('native_map_sha256'),str) or len(geometry['native_map_sha256'])!=64:
        raise ValueError('Native geometry map hash missing')
    if mapping.get('source_kind')!='native_map_readback' or type(mapping.get('connected_requested_lane_link')) is not bool:
        raise ValueError('Native lane-link audit missing')
    if (mapping.get('native_samples_sha256')!=sha(paths[0]) or
        mapping.get('road_geometry_sha256')!=sha(paths[1]) or
        mapping.get('native_map_sha256')!=geometry['native_map_sha256']):
        raise ValueError('Native map audit source hash mismatch')
    if pixels.get('source_kind')!='original_camera_pixels' or pixels.get('native_samples_sha256')!=sha(paths[0]) or pixels.get('video_sha256')!=sha(paths[4]):
        raise ValueError('Pixel audit source hash mismatch')
    visible,total=pixels.get('full_body_and_lane_marking_visible_frames'),pixels.get('approach_frames')
    if type(visible) is not int or type(total) is not int or total<1 or not 0<=visible<=total:
        raise ValueError('Invalid original-pixel visibility count')
    route=[point(p) for p in requested_route_xy_m]
    if len(route)<2:raise ValueError('Requested route incomplete')
    errors=[];completed=False;prior_frame=-1;prior_time=-math.inf
    for row in samples:
        frame,time=row.get('native_frame'),row.get('time_s')
        if type(frame) is not int or frame<=prior_frame or type(time) not in (int,float) or not math.isfinite(time) or time<=prior_time:
            raise ValueError('Native frame/time sequence invalid')
        prior_frame,prior_time=frame,time
        center=point(row.get('native_center_xy_m'))
        forward=point(row.get('native_forward_xy'))
        if abs(math.hypot(*forward)-1)>.01:raise ValueError('Native heading not unit length')
        body=row.get('native_body_xy_m')
        if not isinstance(body,list) or len(body)!=4:raise ValueError('Complete Native body missing')
        body=[point(p) for p in body]
        if -10<=center[0]<=7:
            errors.append(min(distance(center,a,b) for a,b in zip(route,route[1:])))
        if time<=24 and row.get('native_lane_id')==-2:
            if requested_movement=='right_turn' and row.get('native_road_id')==4 and max(p[1] for p in body)<-7 and forward[1]<-.95:
                completed=True
            if requested_movement=='straight_through' and row.get('native_road_id')==2 and min(p[0] for p in body)>7 and forward[0]>.95:
                completed=True
    if not errors:raise ValueError('No observed connector-entry tracking window')
    maximum=max(errors);fraction=visible/total
    return {'fallback1':not mapping['connected_requested_lane_link'] or not completed,
            'fallback2':maximum>.35,'fallback3':fraction<.95,
            'metrics':{'connected_requested_lane_link':mapping['connected_requested_lane_link'],
                       'full_body_requested_exit_observed_by_24s':completed,
                       'maximum_connector_entry_route_error_m':maximum,
                       'approach_pixel_visible_fraction':fraction},
            'source_hashes':{p.name:sha(p) for p in paths},
            'scope':'Source-bound CPU trigger logic; synthetic packets are not physical observations'}
