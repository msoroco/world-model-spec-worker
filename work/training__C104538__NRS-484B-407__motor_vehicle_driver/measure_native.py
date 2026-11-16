"""Saved original Native geometry and motion measurements; no legal verdict."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    path=Path(path)
    if not path.is_file():raise ValueError('Missing required source: '+path.name)
    values=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len(values)<2:raise ValueError('Insufficient original samples: '+path.name)
    return values


def finite(value):return type(value) in (int,float) and math.isfinite(value)


def center(vertices):
    if not isinstance(vertices,list) or len(vertices)<4 or any(
        not isinstance(vertex,list) or len(vertex)<3 or not all(finite(x) for x in vertex[:3])
        for vertex in vertices):raise ValueError('Missing finite original body vertices')
    return [sum(vertex[axis] for vertex in vertices)/len(vertices) for axis in range(3)]


def unwrap(headings):
    if not all(finite(value) for value in headings):raise ValueError('Missing original heading')
    return sum((b-a+180)%360-180 for a,b in zip(headings,headings[1:]))


def barrier_gap(inventory):
    if not isinstance(inventory,list) or len(inventory)<2:
        raise ValueError('Missing original barrier actor geometry')
    gaps=[]
    for left,right in zip(inventory,inventory[1:]):
        a=left['requested'];b=right['requested']
        pa=a['native_xyz_m'];pb=b['native_xyz_m']
        axis=[pb[0]-pa[0],pb[1]-pa[1]]
        length=math.hypot(*axis)
        if length<=0:raise ValueError('Repeated original barrier position')
        axis=[x/length for x in axis]
        project=lambda item:[vertex[0]*axis[0]+vertex[1]*axis[1]
                             for vertex in item['world_vertices_m']]
        first=project(left);second=project(right)
        if len(first)<4 or len(second)<4 or not all(finite(x) for x in first+second):
            raise ValueError('Invalid original barrier actor vertices')
        gaps.append(max(0,min(second)-max(first)))
    return max(gaps)


def analyze(attempt):
    attempt=Path(attempt)
    config=json.loads((attempt/'config.json').read_text())
    context=json.loads((attempt/'native-construction-context.json').read_text())
    if context['case_id']!=config['case_id'] or context['candidate_id']!=config['candidate_id']:
        raise ValueError('Native construction context identity differs')
    if not finite(context.get('driver_eye_offset_assumed_m')):
        raise ValueError('Missing declared assumed driver-eye mount')
    if context['native_road_sha256']!=sha(attempt/'native_road_readback.xodr'):
        raise ValueError('Native map readback hash differs')
    authored_road=attempt/'authored_road.xodr'
    if not authored_road.is_file():authored_road=attempt/'road.xodr'
    authored_road_hash=context.get('authored_road_sha256')
    if authored_road_hash is not None:
        if not authored_road.is_file() or sha(authored_road)!=authored_road_hash:
            raise ValueError('Authored road source hash differs')
    authored_reference=None
    authored_path=attempt/'obstruction.json'
    authored_hash=context.get('authored_obstruction_sha256')
    if authored_hash is not None:
        if not authored_path.is_file() or sha(authored_path)!=authored_hash:
            raise ValueError('Authored obstruction source hash differs')
        authored=json.loads(authored_path.read_text())
        if (authored.get('case_suffix')!=config['case_suffix'] or
            authored.get('road_xodr_sha256')!=sha(authored_road) or
            authored.get('native_actor_spawned') is not False or
            authored.get('physical_opacity_measured') is not False):
            raise ValueError('Authored obstruction source identity differs')
        radius=authored.get('inner_radius_m')
        if not finite(radius) or not 0<radius<500:
            raise ValueError('Invalid authored obstruction radius')
        authored_reference=1000*math.acos(radius/500)/.3048
        if abs(authored_reference-authored['requested_reference_limit_ft'])>1e-6:
            raise ValueError('Authored obstruction limit differs')
    trace=rows(attempt/'trace.jsonl');evidence=rows(attempt/'capture/evidence.jsonl')
    history=rows(attempt/'native_body_history.jsonl')
    viewpoints=rows(attempt/'driver_eye_rays.jsonl')
    mapping=rows(attempt/'video_frames.jsonl')
    expected=config['duration_s']*config['rate_hz']
    if not all(len(series)==expected for series in (trace,evidence,history,viewpoints,mapping)):
        raise ValueError('Original Native source counts differ')
    previous_frame=-1;previous_time=-math.inf
    headings=[];centers=[];signed_velocity=[];direction_distances={'reference_left':[],'reference_right':[]}
    for index,(t,e,h,v,m) in enumerate(zip(trace,evidence,history,viewpoints,mapping)):
        frame=m['native_frame'];time=m['time_s']
        if (type(frame) is not int or frame<=previous_frame or
            not finite(time) or time<=previous_time or m['video_frame']!=index or
            m.get('carla_frame')!=frame):raise ValueError('Original frame map is not monotonic')
        previous_frame=frame;previous_time=time
        if any(source_frame!=frame for source_frame in
            (t.get('frame'),e.get('original_frame'),h.get('native_frame'),v.get('native_frame'))):
            raise ValueError('Original Native frame join differs')
        if any(not finite(value) or abs(value-time)>1e-4 for value in
            (t.get('time_s'),e.get('recording_time_s'),h.get('time_s'),v.get('time_s'))):
            raise ValueError('Original Native time join differs')
        native_body=h['ego_body_vertices_m'];captured_body=e['ego']['body_vertices_m']
        if native_body!=captured_body or t['c104538_native']['ego_body_vertices_m']!=native_body:
            raise ValueError('Original ego body differs from capture evidence')
        c=center(native_body);centers.append(c)
        heading=h['ego_heading_deg'];headings.append(heading)
        velocity=t['velocity_mps']
        if not isinstance(velocity,list) or len(velocity)<2 or not all(finite(x) for x in velocity[:2]):
            raise ValueError('Missing observed Native velocity')
        signed_velocity.append(velocity[0]*math.cos(math.radians(heading))+
                               velocity[1]*math.sin(math.radians(heading)))
        if h['ego_center_xyz_m']!=t['position_m']:
            raise ValueError('Original ego position differs from trace')
        for role in direction_distances:
            if v['views'][role].get('driver_eye_point_is_assumed') is not True:
                raise ValueError('Driver-eye point must retain its assumed status')
            view=v['views'][role]['driver_viewpoint_xyz_m']
            if not isinstance(view,list) or len(view)!=3 or not all(finite(x) for x in view):
                raise ValueError('Missing original approaching driver viewpoint')
            if v['views'][role]!=t['approaching_driver_views'][role]:
                raise ValueError('Original approaching driver view differs from trace')
            direction_distances[role].append(math.dist(view,c))
    samples=context.get('waypoint_elevation_samples',[])
    if len(samples)<2:raise ValueError('Missing original Native crest readback')
    crest_errors=[abs(row['native_waypoint_z_m']-row['authored_road_height_m'])
                  for row in samples]
    if not all(finite(error) for error in crest_errors):
        raise ValueError('Invalid original crest readback')
    gap=barrier_gap(context.get('barrier_inventory'))
    heading_change=unwrap(headings)
    sampled_path=sum(math.dist(a,b) for a,b in zip(centers,centers[1:]))
    orientation=(headings[-1]-headings[0]+180)%360-180
    reversal=abs(heading_change)>=150 and abs(orientation)>=150 and sampled_path>=5
    backing=any(value<-.2 for value in signed_velocity)
    result={'format':'c104538-saved-native-measurement-v1',
            'case_id':config['case_id'],'candidate_id':config['candidate_id'],
            'original_frames':expected,'observed_heading_change_deg':heading_change,
            'endpoint_orientation_change_deg':orientation,'sampled_body_path_m':sampled_path,
            'reverse_motion_observed':backing,'engineering_reversal_observed':reversal,
            'maximum_native_crest_height_error_m':max(crest_errors),
            'maximum_native_barrier_box_gap_m':gap,
            'fallback1_trigger_measured':max(crest_errors)>.15,
            'fallback2_trigger_measured':gap>.05,
            'fallback3_original_pixel_trigger_measured':False,
            'approaching_assumed_eye_to_ego_center_distance_m':{
                role:{'minimum':min(values),'maximum':max(values)}
                for role,values in direction_distances.items()},
            'actual_body_visibility_proven':False,'original_pixel_visibility_proven':False,
            'authored_center_reference_limit_ft':authored_reference,
            'authored_road_source_sha256':authored_road_hash,
            'authored_obstruction_source_sha256':authored_hash,
            'legal_verdict_claimed':False,'accepted':False,
            'source_sha256':{name:sha(attempt/name) for name in (
                'config.json','native-construction-context.json','native_road_readback.xodr',
                'trace.jsonl','capture/evidence.jsonl','native_body_history.jsonl',
                'driver_eye_rays.jsonl','video_frames.jsonl')}}
    if authored_hash is not None:
        result['source_sha256']['obstruction.json']=authored_hash
    if authored_road_hash is not None:
        result['source_sha256'][authored_road.name]=authored_road_hash
    return result
