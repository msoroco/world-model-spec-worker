"""Source-bound Walk crossing observation; no legal right-of-way verdict."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_rows(path: Path) -> list[dict]:
    require(path.is_file(), 'Missing required source: '+path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def rectangle(body, label: str) -> tuple[float,float,float,float]:
    require(isinstance(body,list) and len(body)==4 and all(
        isinstance(p,list) and len(p)==2 and all(type(v) in (int,float) and math.isfinite(v) for v in p)
        for p in body), 'Missing or invalid original '+label+' body')
    x=[p[0] for p in body];y=[p[1] for p in body]
    require(min(x)<max(x) and min(y)<max(y), 'Degenerate original '+label+' body')
    return min(x),max(x),min(y),max(y)


def intersects(a: tuple[float,float,float,float],b: tuple[float,float,float,float]) -> bool:
    return a[0]<=b[1] and a[1]>=b[0] and a[2]<=b[3] and a[3]>=b[2]


def analyze(folder: Path, review: dict | None = None) -> dict:
    folder=Path(folder)
    geometry_path=folder/'road_geometry.json'
    require(geometry_path.is_file(),'Missing required source: road_geometry.json')
    geometry=json.loads(geometry_path.read_text())
    signal_id=geometry.get('walk_signal_id')
    require(geometry.get('cell_id')=='C111256' and type(signal_id) is int and signal_id>0 and
            geometry.get('crosswalk_y_range_m')==[-12.0,-10.0] and
            geometry.get('bus_lane_x_range_m')==[0.0,3.5],
            'Original Walk/crosswalk geometry or signal identity differs')
    synthetic=geometry.get('synthetic_diagnostic') is True
    if not synthetic:
        require(review is not None and review.get('official_signal_verified') is True and
                review.get('governance_verified') is True and
                review.get('pedestrian_heading_verified') is True,
                'Original pedestrian Walk review absent or unverified')
    samples=read_rows(folder/'native_samples.jsonl')
    mapping=read_rows(folder/'video_frames.jsonl')
    require(samples and len(samples)==len(mapping) and
            (synthetic or len(review.get('observations',[]))==len(samples)),
            'Original frame map/source or review count differs')
    conflict=(0.0,3.5,-12.0,-10.0)
    walk_frames=0;directed_frames=0;simultaneous=[];bus_frames=[];ped_frames=[]
    previous_frame=-1;previous_time=-1.0
    for index,(sample,frame) in enumerate(zip(samples,mapping)):
        ident=sample.get('native_frame');time=sample.get('time_s')
        require(type(ident) is int and ident>previous_frame and
                type(time) in (int,float) and math.isfinite(time) and time>previous_time and
                frame.get('native_frame')==ident and frame.get('video_frame')==index and
                abs(frame.get('time_s',float('inf'))-time)<1e-4,
                'Original Native/video frame or timestamp join differs')
        previous_frame=ident;previous_time=time
        require(sample.get('walk_signal_actor_id')==signal_id and
                type(sample.get('pedestrian_actor_id')) is int and sample['pedestrian_actor_id']>0 and
                type(sample.get('bus_actor_id')) is int and sample['bus_actor_id']>0 and
                sample['bus_actor_id']!=sample['pedestrian_actor_id'] and
                sample['walk_signal_actor_id']!=sample['pedestrian_actor_id'],
                'Original bus, pedestrian or signal identity differs')
        observed=review['observations'][index] if review is not None and not synthetic else None
        if observed is not None:
            require(observed.get('native_frame')==ident and
                    observed.get('signal_actor_id')==signal_id,
                    'Original review/Native frame or signal identity differs')
        display=observed['display'] if observed is not None else sample.get('walk_signal_display_observed')
        require(display in ('Walk','DontWalk','Wait','Unknown'),
                'Original pedestrian signal display absent')
        facing=observed['pedestrian_facing_signal'] if observed is not None else sample.get('pedestrian_facing_signal')
        require(type(facing) is bool,
                'Original pedestrian facing observation absent')
        if not synthetic:
            require(sample.get('walk_signal_display_observed')=='Unknown' and
                    sample.get('display_source')=='authored_debug_text_pending_original_pixel_review' and
                    sample.get('pedestrian_facing_source')=='authored_route_pending_original_heading_review',
                    'Original raw Walk display or pedestrian heading state differs')
        provenance=sample.get('speed_provenance')
        expected_provenance='synthetic_native_sample' if synthetic else 'native_measured'
        require(provenance==expected_provenance and
                type(sample.get('bus_speed_mps')) in (int,float) and
                math.isfinite(sample['bus_speed_mps']) and sample['bus_speed_mps']>=0,
                'Original speed provenance or value absent')
        bus=rectangle(sample.get('bus_body_xy_m'),'bus')
        pedestrian=rectangle(sample.get('pedestrian_body_xy_m'),'pedestrian')
        bus_inside=intersects(bus,conflict)
        ped_inside=intersects(pedestrian,conflict)
        active=display=='Walk' and facing
        walk_frames+=int(display=='Walk')
        directed_frames+=int(active and ped_inside)
        if bus_inside:bus_frames.append(index)
        if active and ped_inside:ped_frames.append(index)
        if active and ped_inside and bus_inside:simultaneous.append(index)
    return {'format':'c111256-source-walk-measurement','frames':len(samples),
            'walk_display_frames':walk_frames,
            'directed_pedestrian_conflict_frames':directed_frames,
            'bus_conflict_frames':len(bus_frames),
            'simultaneous_conflict_frames':len(simultaneous),
            'first_bus_conflict_frame':bus_frames[0] if bus_frames else None,
            'first_directed_pedestrian_conflict_frame':ped_frames[0] if ped_frames else None,
            'first_simultaneous_conflict_frame':simultaneous[0] if simultaneous else None,
            'source_sha256':{name:sha(folder/name) for name in
                ('road_geometry.json','native_samples.jsonl','video_frames.jsonl',
                 *(['official-walk-review.json'] if review is not None and not synthetic else []))},
            'synthetic_diagnostic':synthetic,
            'physical_acceptance_claimed':False,'legal_verdict_claimed':False}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path)
    print(json.dumps(analyze(parser.parse_args().folder),sort_keys=True))
