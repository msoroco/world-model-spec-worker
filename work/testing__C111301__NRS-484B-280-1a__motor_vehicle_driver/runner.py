"""Construction geometry and engineering controller for a wheelchair encounter.

The 3 s brake lookahead is an authored control policy, not a due-care legal rule.
"""
import argparse
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def load_scene(path=None):
    scene=json.loads(Path(path or ROOT/'scene.json').read_text())
    if (scene['law_id'],scene['cell_id'],scene['actor'],scene['layout'],
        scene['maneuver'],scene['control']) != (
            'NRS-484B-280-1a','C111301','motor_vehicle_driver',
            'intersection','travel','pedestrian'):
        raise ValueError('wrong frozen assignment or grounded cell')
    if not (scene['ego_start_xy_m'][0]<scene['pedestrian_path_start_xy_m'][0]
            <scene['ego_exit_xy_m'][0]):
        raise ValueError('ego route does not cross pedestrian path')
    if not (scene['pedestrian_path_start_xy_m'][1]<scene['ego_lane_bounds_y_m'][0]
            <scene['ego_lane_bounds_y_m'][1]<scene['pedestrian_path_end_xy_m'][1]):
        raise ValueError('wheelchair path does not cross ego lane')
    if scene.get('wheelchair_path_setup') not in (None,'clear_path','crossing'):
        raise ValueError('unsupported wheelchair path setup')
    return scene


def bounds(vertices):
    if not isinstance(vertices,list) or len(vertices)<4 or any(
        not isinstance(v,list) or len(v)<3 or any(
            type(x) not in (int,float) or not math.isfinite(x) for x in v[:3])
        for v in vertices):
        raise ValueError('missing finite original body footprint')
    return (min(v[0] for v in vertices),min(v[1] for v in vertices),
            max(v[0] for v in vertices),max(v[1] for v in vertices))


def gap(a,b):
    a0,a1,a2,a3=bounds(a);b0,b1,b2,b3=bounds(b)
    return math.hypot(max(a0-b2,b0-a2,0),max(a1-b3,b1-a3,0))


def wheelchair_body(person,chair):
    """Require original body sources for a person and a distinct manual chair."""
    if person.get('role')!='person_in_manual_wheelchair' or chair.get('kind')!='manual_wheelchair':
        raise ValueError('manual wheelchair identity is not source-confirmed')
    if not person.get('source_ref') or not chair.get('source_ref'):
        raise ValueError('person or chair original source missing')
    person_body=person.get('body_vertices_m');chair_body=chair.get('body_vertices_m')
    if gap(person_body,chair_body)>.75:
        raise ValueError('person and wheelchair bodies are not spatially associated')
    return person_body+chair_body


def encounter(scene,ego_body,person,chair,ego_speed_mps,pedestrian_speed_mps):
    if any(type(value) not in (int,float) or not math.isfinite(value) or value<0
           for value in (ego_speed_mps,pedestrian_speed_mps)):
        raise ValueError('invalid original nonnegative speed')
    combined=wheelchair_body(person,chair)
    ex0,ey0,ex1,ey1=bounds(ego_body)
    px0,py0,px1,py1=bounds(combined)
    longitudinal_gap=max(px0-ex1,0)
    surface_gap=gap(ego_body,combined)
    time_to_path=(longitudinal_gap/ego_speed_mps if ego_speed_mps>0 else None)
    lane_low,lane_high=scene['ego_lane_bounds_y_m']
    pedestrian_in_or_approaching_lane=(py1>=lane_low and py0<=lane_high) or (
        pedestrian_speed_mps>0 and py1<lane_low)
    return {'surface_gap_m':surface_gap,'longitudinal_gap_m':longitudinal_gap,
            'time_to_path_s':time_to_path,'pedestrian_in_or_approaching_lane':pedestrian_in_or_approaching_lane,
            'person_body_source':person['source_ref'],'chair_body_source':chair['source_ref'],
            'collision_observed':surface_gap==0}


def control(scene,measurement):
    """Brake for a measured conflict; do not assign a legal due-care verdict."""
    if not {'time_to_path_s','pedestrian_in_or_approaching_lane','surface_gap_m'}<=measurement.keys():
        raise ValueError('missing source-bound encounter measurement')
    ttc=measurement['time_to_path_s']
    brake=bool(measurement['pedestrian_in_or_approaching_lane'] and
               (measurement['surface_gap_m']==0 or
                (ttc is not None and ttc<=scene['engineering_ttc_brake_s'])))
    return {'throttle':0.0 if brake else .25,'brake':1.0 if brake else 0.0,
            'steer':0.0,'legal_due_care_verdict':None}


def check():
    scene=load_scene()
    print(json.dumps({'crossing_geometry_checked':True,
                      'manual_wheelchair_native_asset_requires_native_preflight':True,
                      'lookahead_is_engineering_only':True}))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args()
    if args.check:check();return
    if not args.output_dir:parser.error('--output-dir required for Native capture')
    from native_capture import run_native
    run_native(load_scene(),Path(args.output_dir),args.host,args.port)


if __name__=='__main__':main()
