"""Exact C393410 route entrypoint; CARLA loads only after source review."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from route_measure import load_review

ASSIGNMENT='testing__C393410__LVMC-11-48-060__motor_vehicle_driver'
VARIANTS={'through_no_enroute':('non_truck','through','none'),'pickup_required':('non_truck','through','pick_up'),'delivery_required':('non_truck','through','delivery'),'essential_required':('non_truck','through','essential_use'),'local_non_through':('non_truck','local','none'),'designated_route':('truck_route','through','none')}
CAMERAS={'overview':[1920,1080],'approach':[1280,720],'reference_corner':[1280,720],'driver_reference':[1280,720]}


def check(root:Path)->dict:
    root=Path(root).resolve();config=json.loads((root/'config.json').read_text());spec=json.loads((root/'case-spec.json').read_text());control=json.loads((root/'controller.json').read_text());case_id=config.get('selected_case_id')
    if case_id not in {ASSIGNMENT+'__'+suffix for suffix in VARIANTS}:
        raise ValueError('Selected truck-route case differs')
    if (config.get('law_id'),config.get('cell_id'),config.get('actor'))!=('LVMC-11-48-060','C393410','motor_vehicle_driver') or spec.get('case_id')!=case_id:
        raise ValueError('Exact law, cell, actor or case differs')
    named={camera.get('name'):[camera.get('width'),camera.get('height')] for camera in config.get('cameras',[])}
    if config.get('rate_hz')!=20 or config.get('duration_s')!=45 or len(config.get('cameras',[]))!=4 or named!=CAMERAS:
        raise ValueError('Four synchronized 20 Hz views required')
    if tuple(spec.get(key) for key in ('street_class','route_use','enroute_purpose'))!=VARIANTS[case_id.split('__')[-1]]:
        raise ValueError('Selected route comparison variable differs')
    speed=control.get('target_speed_mps')
    if type(speed) not in (int,float) or not 1<=speed<=8:
        raise ValueError('Bounded original route speed required')
    return {'case_id':case_id,'speed':speed,'source_gate':'reviewed original municipal truck-route designations, non-truck connector, complete route and required enroute activity before Native'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--output-dir',type=Path,default=Path.cwd());parser.add_argument('--packet',type=Path);parser.add_argument('--source-root',type=Path);parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=2000);args=parser.parse_args()
    selected=check(args.output_dir)
    if args.check:
        print(json.dumps({**selected,'native_started':False}));return
    packet=args.packet or os.environ.get('C393410_ROUTE_REVIEW_PACKET');source_root=args.source_root or os.environ.get('C393410_ROUTE_SOURCE_ROOT')
    if not packet or not source_root:raise ValueError('Original reviewed route packet and source root required')
    load_review(Path(packet),Path(source_root),selected['case_id'])
    from native_entry import capture_original
    print(json.dumps(capture_original(args.output_dir,args.output_dir,packet,source_root,host=args.host,port=args.port),sort_keys=True))

if __name__=='__main__':main()
