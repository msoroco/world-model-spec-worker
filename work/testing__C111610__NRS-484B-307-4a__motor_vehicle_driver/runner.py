"""Source-gated left-arrow turn and adjacent-crosswalk yield construction."""
import argparse
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def load_scene(path=None):
    scene=json.loads(Path(path or ROOT/'scene.json').read_text())
    if (scene['law_id'],scene['cell_id'],scene['actor'],scene['layout'],
        scene['maneuver'],scene['control'])!=('NRS-484B-307-4a','C111610',
        'motor_vehicle_driver','intersection','turn','pedestrian'):
        raise ValueError('wrong frozen law, actor or grounded cell')
    if scene['arrow_direction']!='left' or scene['facing_head_id'] is None:
        raise ValueError('authored arrow direction or ego-facing head missing')
    if scene['ego_start_xy_m'][0]>=scene['turn_entry_x_m'] or scene['turn_center_xy_m'][1]>=scene['ego_exit_xy_m'][1]:
        raise ValueError('left-turn approach or exit is not spatially ordered')
    left,bottom,right,top=scene['adjacent_crosswalk_bounds_m']
    if not (left<scene['ego_exit_xy_m'][0]<right and
            scene['turn_center_xy_m'][1]<bottom<top<scene['ego_exit_xy_m'][1]):
        raise ValueError('adjacent crosswalk does not intersect left-turn exit')
    if scene.get('crosswalk_setup') not in ('clear','occupied'):
        raise ValueError('unknown adjacent-crosswalk setup')
    traffic_setup = scene.get('other_traffic_setup', 'absent')
    if traffic_setup not in ('absent', 'lawful_entered'):
        raise ValueError('unknown other-traffic setup')
    if scene['case_id'].endswith('__lawful_traffic_yield') != (traffic_setup == 'lawful_entered'):
        raise ValueError('traffic setup does not match exact case')
    if traffic_setup == 'lawful_entered':
        start = scene.get('other_vehicle_entry_start_xy_m')
        conflict = scene.get('other_vehicle_conflict_xy_m')
        end = scene.get('other_vehicle_end_xy_m')
        if (not all(isinstance(p, list) and len(p) == 2 for p in (start, conflict, end)) or
                not (start[0] == conflict[0] == end[0] and start[1] < conflict[1] < end[1]) or
                scene.get('other_vehicle_signal_head_id') is None or
                type(scene.get('other_vehicle_target_speed_mps')) not in (int, float) or
                not 0 < scene['other_vehicle_target_speed_mps'] <= 3):
            raise ValueError('lawful other-vehicle entry path or original signal missing')
    sx,sy=scene['pedestrian_start_xy_m'];ex,ey=scene['pedestrian_end_xy_m']
    px,py=scene['pedestrian_entry_start_xy_m']
    if not (left<=sx<=right and bottom<=sy<=top and ex>right and ey==sy and
            px<left and py==sy and scene['pedestrian_signal_head_id'] is not None and
            type(scene['pedestrian_target_speed_mps']) in (int,float) and
            0<scene['pedestrian_target_speed_mps']<=2):
        raise ValueError('pedestrian path must start inside adjacent crosswalk and leave it')
    return scene


def sole_turn_arrow(signal,scene,frame):
    if signal.get('source_verified') is not True or not signal.get('source_ref'):
        raise ValueError('ego-facing signal-head source missing')
    if signal.get('head_id')!=scene['facing_head_id'] or signal.get('observed_frame')!=frame:
        raise ValueError('signal head is not the ego-facing original head/frame')
    expected=[{'color':'green','shape':'arrow','direction':scene['arrow_direction']}]
    if signal.get('illuminated_indications')!=expected:
        raise ValueError('sole illuminated green turn arrow not observed')
    return True


def bounds(vertices):
    if not isinstance(vertices,list) or len(vertices)<4 or any(
        not isinstance(point,list) or len(point)<3 or any(type(value) not in (int,float) or
        not math.isfinite(value) for value in point[:3]) for point in vertices):
        raise ValueError('original finite body vertices required')
    return (min(p[0] for p in vertices),min(p[1] for p in vertices),
            max(p[0] for p in vertices),max(p[1] for p in vertices))


def overlaps(first,second):
    a=bounds(first);b=second
    return a[0]<b[2] and b[0]<a[2] and a[1]<b[3] and b[1]<a[3]


def lawful_occupants(participants,scene):
    present=[]
    for person in participants:
        if person.get('role')!='pedestrian':continue
        if not person.get('source_ref') or not person.get('lawful_presence_source'):
            raise ValueError('pedestrian body or lawful-presence source missing')
        body=person.get('body_vertices_m')
        bounds(body)
        if person.get('lawfully_present') is True and overlaps(body,scene['adjacent_crosswalk_bounds_m']):
            present.append(person.get('id'))
    return present


def turn_route(scene):
    return [scene['ego_start_xy_m'],[scene['turn_entry_x_m'],scene['ego_start_xy_m'][1]],
            scene['turn_center_xy_m'],scene['ego_exit_xy_m']]


def route_steer(scene,ego_xy,heading_deg):
    """A bounded steer command toward successive points of the left turn."""
    if type(heading_deg) not in (int,float) or not math.isfinite(heading_deg):
        raise ValueError('original ego heading required for route control')
    x,y=ego_xy
    if not all(type(v) in (int,float) and math.isfinite(v) for v in (x,y)):
        raise ValueError('original ego position required for route control')
    route=turn_route(scene)
    target=(route[1] if x<scene['turn_entry_x_m']-2 else
            route[2] if y<scene['turn_center_xy_m'][1]-1 else route[3])
    desired=math.degrees(math.atan2(target[1]-y,target[0]-x))
    error=(desired-heading_deg+180)%360-180
    return max(-1,min(1,error/45))


def control(scene,signal,frame,ego_body_vertices,participants,other_traffic,
            ego_heading_deg=None):
    sole_turn_arrow(signal,scene,frame)
    occupants=lawful_occupants(participants,scene)
    lawful_traffic=[]
    for vehicle in other_traffic:
        if not vehicle.get('source_ref') or not vehicle.get('lawful_presence_source'):
            raise ValueError('other intersection traffic source missing')
        if vehicle.get('lawfully_using_intersection') is True:lawful_traffic.append(vehicle.get('id'))
    right=bounds(ego_body_vertices)[2]
    occupied=bool(occupants or lawful_traffic)
    if occupied and right>scene['turn_entry_x_m']:
        return {'throttle':0,'brake':1,'steer':0,'hold_target_met':False,
                'occupant_ids':occupants,'traffic_ids':lawful_traffic}
    if occupied:
        return {'throttle':0,'brake':1,'steer':0,'hold_target_met':True,
                'occupant_ids':occupants,'traffic_ids':lawful_traffic}
    steer=route_steer(scene,[(bounds(ego_body_vertices)[0]+bounds(ego_body_vertices)[2])/2,
                              (bounds(ego_body_vertices)[1]+bounds(ego_body_vertices)[3])/2],
                       ego_heading_deg)
    return {'throttle':.2,'brake':0,'steer':steer,'hold_target_met':True,
            'occupant_ids':[],'traffic_ids':[]}


def check(scene_path=None):
    scene=load_scene(scene_path)
    print(json.dumps({'left_turn_route':turn_route(scene),
          'adjacent_crosswalk_geometry_checked':True,'ego_facing_head_requires_native_source':True}))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--scene')
    parser.add_argument('--output-dir');parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000);args=parser.parse_args()
    if args.check:check(args.scene);return
    if not args.output_dir:parser.error('--output-dir required for Native capture')
    from native_capture import run_native
    run_native(load_scene(args.scene),Path(args.output_dir),args.host,args.port)


if __name__=='__main__':main()
