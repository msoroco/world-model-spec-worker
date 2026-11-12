"""Saved-only passing and constructed occluder geometry from original sources."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from three_lane_finalizer import analyze as analyze_lanes
from three_lane_passing_finalizer import measure_passing_sources as base_passing
from three_lane_passing_finalizer import build_result


def measure_occluded_sources(attempt):
    root=Path(attempt)
    measured=base_passing(root)
    path=root/'occluder_frames.jsonl'
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: occluder_frames.jsonl')
    rows=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    passing=measured['observations']
    lane_rows=[json.loads(line) for line in (root/'three_lane_frames.jsonl').read_text().splitlines() if line.strip()]
    if len(rows)!=len(passing) or len(rows)!=len(lane_rows):
        raise ValueError('Original occluder and passing frames differ')
    geometry=[]
    for row, observation, lane in zip(rows,passing,lane_rows):
        if ((row.get('frame'),row.get('time_s')) !=
                (observation['frame'],observation['time_s']) or
                not row.get('occluder_actor_id') or
                not row.get('occluder_blueprint','').startswith('static.prop.')):
            raise ValueError('Original occluder frame or actor identity differs')
        vertices=row.get('occluder_vertices_xyz')
        if not isinstance(vertices,list) or len(vertices)!=8:
            raise ValueError('Original occluder body vertices missing')
        if any(not isinstance(v,list) or len(v)!=3 for v in vertices):
            raise ValueError('Original occluder body vertex invalid')
        xs=[float(v[0]) for v in vertices]
        ys=[float(v[1]) for v in vertices]
        zs=[float(v[2]) for v in vertices]
        height=max(zs)-min(zs)
        ego=row['ego_center_xy']
        tangent=lane['road_travel_tangent_xy']
        forward_distance=((sum(xs)/len(xs)-ego[0])*tangent[0] +
                          (sum(ys)/len(ys)-ego[1])*tangent[1])
        if height<1.8 or forward_distance<15:
            raise ValueError('Constructed occluder dimensions or distance missing')
        geometry.append({'frame':row['frame'],'time_s':row['time_s'],
                         'forward_distance_m':forward_distance,
                         'height_m':height,'lateral_span_m':max(ys)-min(ys),
                         'actor_id':row['occluder_actor_id']})
    measured['sources']['occluder_frames.jsonl']=sha256(path.read_bytes()).hexdigest()
    measured['occluder_geometry']=geometry
    measured['physical_sight_occlusion_confirmed']=False
    return measured


def analyze(attempt):
    report=analyze_lanes(attempt)
    if not report['case_id'].endswith('__center_passing_occluded'):
        raise ValueError('Wrong exact occluded passing case identity')
    measured=measure_occluded_sources(attempt)
    report['measurements']['passing_observation']={
        'method':'measure_occluded_sources','value':measured,'sources':measured['sources']}
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    output=Path(args.output)
    if output.exists():
        raise ValueError('Retain prior occluded passing analysis')
    report=analyze(args.attempt)
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt,build_result(args.attempt,report))


if __name__=='__main__':
    main()
