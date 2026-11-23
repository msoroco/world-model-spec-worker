"""Portable geometry/controller policy for exact 400(2)(a) approach cases.

The surveyed Native map packet must supply the source geometry; this module
does not claim a particular CARLA map has already been surveyed.
"""
import argparse
import json
import math
from pathlib import Path

from approach import validate_context

SUFFIXES = ('near_centerline', 'farther_from_centerline',
            'imaginary_near_centerline', 'imaginary_farther_from_centerline')


def build(case_id, map_packet):
    suffix = case_id.split('__')[-1]
    if suffix not in SUFFIXES:
        raise ValueError('unassigned exact case')
    context = map_packet.get('context')
    if not isinstance(context, dict):
        raise ValueError('surveyed Native intersection context missing')
    a, direction = validate_context(context)
    imaginary = suffix.startswith('imaginary_')
    if imaginary != (context['centerline_kind'] == 'imaginary_equidistant'):
        raise ValueError('case/centerline construction mismatch')
    if not map_packet.get('source_sha256') or not map_packet.get('map_name'):
        raise ValueError('source-hashed Native map survey missing')
    if not map_packet.get('left_turn_route_waypoint_ids') or not map_packet.get('ego_blueprint_id'):
        raise ValueError('left-turn route or ego vehicle blueprint missing')
    # Engineering centers 1.7 and 2.7 m from the oriented centerline; the
    # legal phrase "nearest" has no encoded numeric cutoff.
    offset = 1.7 if 'near_centerline' in suffix and 'farther' not in suffix else 2.7
    if offset >= context['approach_half_width_m']:
        raise ValueError('approach center would leave sourced right half')
    start = [a[0] + 8 * direction[0] + offset * direction[1],
             a[1] + 8 * direction[1] - offset * direction[0]]
    return {'case_id':case_id,'map_name':map_packet['map_name'],
            'survey_source_sha256':map_packet['source_sha256'],
            'ego_blueprint_id':map_packet['ego_blueprint_id'],
            'spawn_xy_m':start,
            'approach_target_lateral_offset_m':offset,
            'left_turn_route_waypoint_ids':map_packet['left_turn_route_waypoint_ids'],
            'controller_policy':{'target_speed_mps':7.0,'steer_gain':.45,
                                 'brake_on_route_end':True},
            'camera_plan':map_packet['camera_plan'],
            'duration_s':45,'rate_hz':20,
            'required_original_sources':['intersection-context.json',
                                          'approach-history.jsonl','video_frames.jsonl'],
            'legal_lateral_cutoff':None}


def control(position_xy_m, heading_rad, target_xy_m, speed_mps, *, target_speed_mps=7.0):
    """Simple bounded waypoint tracking; target offset is fixed by case setup."""
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in
           (*position_xy_m,heading_rad,*target_xy_m,speed_mps,target_speed_mps)):
        raise ValueError('nonfinite original control sample')
    if speed_mps < 0 or target_speed_mps <= 0:
        raise ValueError('invalid speed')
    dx,dy=target_xy_m[0]-position_xy_m[0],target_xy_m[1]-position_xy_m[1]
    if math.hypot(dx,dy)<.5:
        return {'throttle':0.0,'brake':1.0,'steer':0.0}
    error=(math.atan2(dy,dx)-heading_rad+math.pi)%(2*math.pi)-math.pi
    steer=max(-1.0,min(1.0,.45*error))
    return {'throttle':max(0.0,min(.35,(target_speed_mps-speed_mps)*.1)),
            'brake':max(0.0,min(1.0,(speed_mps-target_speed_mps)*.2)),
            'steer':steer}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--map-packet',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    result=build(args.case,json.loads(Path(args.map_packet).read_text()))
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
