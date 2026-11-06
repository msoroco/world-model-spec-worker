"""Proposed Native bicycle/motorist source capture; only --check runs on CPU.

This runner requires an exclusively owned CARLA endpoint. It does not infer
intent, legal interference, accepted recording status, or video compatibility.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import traceback

from cameras import camera_plan
from engineering import CANDIDATES,parameters
from geometry import check as geometry_check,open_drive

HERE=Path(__file__).resolve().parent
CASES=('witness_1','witness_2')
RATE_HZ=20
FRAMES=480

def check(case:str,candidate:str)->dict:
    if case not in CASES or candidate not in CANDIDATES:raise ValueError('Unknown exact bicycle case/candidate')
    geometry=geometry_check();plan=parameters(case,candidate);cameras=camera_plan(candidate)
    if len(cameras)!=4 or len({c['name'] for c in cameras})!=4:
        raise ValueError('Four distinct original views required')
    if [c['name'] for c in cameras]!=plan['knobs']['camera_profile']:
        raise ValueError('Camera and construction profile differ')
    if (plan['law_id'],plan['cell_id'])!=('NRS-484B-270-7a','C111294') or plan['intent_asserted']:
        raise ValueError('Frozen case or intent declaration differs')
    return {'passed':True,'case':case,'candidate':candidate,'geometry':geometry,
            'camera_names':[c['name'] for c in cameras],
            'native_imported':False,'physical_or_legal_outcome_claimed':False}

def footprint(actor):
    vertices=actor.bounding_box.get_world_vertices(actor.get_transform())
    points=sorted({(round(p.x,5),round(p.y,5)) for p in vertices})
    if len(points)!=4:raise RuntimeError('Original actor lacks four distinct ground corners')
    center=actor.get_transform().location
    angle=math.radians(actor.get_transform().rotation.yaw)
    front=(math.cos(angle),math.sin(angle));right=(-front[1],front[0])
    return [list(p) for p in sorted(points,key=lambda p:math.atan2(
        (p[1]-center.y)*front[0]-(p[0]-center.x)*front[1],
        (p[0]-center.x)*front[0]+(p[1]-center.y)*front[1]))]

def sample(actor,mapping,actor_class):
    transform=actor.get_transform();velocity=actor.get_velocity()
    waypoint=mapping.get_waypoint(transform.location,project_to_road=False)
    if waypoint is None:raise RuntimeError('Original actor lost Native lane projection')
    return {'actor_id':actor.id,'blueprint_id':actor.type_id,'declared_class':actor_class,
            'native_road_id':waypoint.road_id,'native_lane_id':waypoint.lane_id,
            'center_xy_m':[transform.location.x,transform.location.y],
            'heading_deg':transform.rotation.yaw,'body_xy_m':footprint(actor),
            'speed_mps':math.hypot(velocity.x,velocity.y),
            'control_brake':float(actor.get_control().brake)}

def execute(case: str, candidate: str, output: Path, host: str, port: int) -> dict:
    """Run the source-bound Native/Core/camera acquisition on an owned endpoint."""
    from runner_capture import execute as capture_execute
    check(case,candidate)
    config_path=Path(__file__).resolve().with_name('config.json')
    if not config_path.is_file():
        raise ValueError('Exact materialized config.json required')
    config=json.loads(config_path.read_text())
    if config.get('case_suffix')!=case or config.get('candidate_id')!=candidate:
        raise ValueError('Exact case/candidate configuration differs')
    return capture_execute(config,output,host,port)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',choices=CASES)
    parser.add_argument('--candidate',choices=CANDIDATES)
    parser.add_argument('--check',action='store_true');parser.add_argument('--execute',action='store_true')
    parser.add_argument('--output',type=Path);parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--host');parser.add_argument('--port',type=int)
    args=parser.parse_args()
    config_path=Path(__file__).resolve().with_name('config.json')
    config=json.loads(config_path.read_text()) if config_path.is_file() else {}
    case=args.case or config.get('case_suffix')
    candidate=args.candidate or config.get('candidate_id')
    if args.output_dir is not None:args.execute=True
    if args.check==args.execute:raise SystemExit('Choose exactly one of --check or --execute')
    if args.check:print(json.dumps(check(case,candidate),sort_keys=True))
    else:
        destination=args.output_dir or args.output
        if destination is None or args.host is None or args.port is None:
            raise SystemExit('Native execution requires output directory, host and port')
        print(json.dumps(execute(case,candidate,destination,args.host,args.port)))
