"""Saved CPU measurements of authored 3(a) routes; no physical observation."""
import hashlib
import json
import math
from pathlib import Path


def measure(directory):
    directory=Path(directory)
    map_bytes=(directory/'scene.xodr').read_bytes()
    results={}
    for case in ('controlled_1','controlled_2'):
        path=directory/f'route-{case}.json'
        data=path.read_bytes();points=json.loads(data)
        first=(-10,0);second=(40,-3.5)
        first_index=next(i for i,p in enumerate(points) if p==list(first))
        first_end=next(i for i,p in enumerate(points) if p==[-3,7]) if case=='controlled_1' else None
        through_interval=[p for p in points if -9<=p[0]<=20 and abs(p[1])<1e-6]
        through_lane_interval=[p for p in points if 30<=p[0]<=40 and abs(p[1]+3.5)<1e-6]
        left_exit=points[-1][0]
        results[case]={
            'route_sha256':hashlib.sha256(data).hexdigest(),
            'sample_count':len(points),
            'authored_path_length_m':round(sum(math.dist(a,b) for a,b in zip(points,points[1:])),4),
            'first_center_turn_opportunity_index':first_index,
            'first_opportunity_left_exit_index':first_end,
            'center_lane_through_first_opportunity_samples':len(through_interval),
            'later_through_lane_samples':len(through_lane_interval),
            'left_exit_x_m':left_exit,
            'commanded_purpose':('left_turn_from_center_at_first_opportunity' if case=='controlled_1'
                                 else 'through_travel_then_later_left_from_through_lane'),
            'commanded_purpose_is_driver_intent_observation':False,
        }
    assert results['controlled_1']['first_opportunity_left_exit_index']==1000
    assert results['controlled_2']['center_lane_through_first_opportunity_samples']>250
    assert results['controlled_2']['later_through_lane_samples']>90
    return {'passed':True,'source_kind':'authored_cpu_route',
            'map_sha256':hashlib.sha256(map_bytes).hexdigest(),'cases':results,
            'physical_center_lane_occupancy_verified':False,
            'driver_purpose_verified':False,'legal_outcome_verdict':None}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('directory');args=parser.parse_args()
    print(json.dumps(measure(args.directory),indent=2,sort_keys=True))
