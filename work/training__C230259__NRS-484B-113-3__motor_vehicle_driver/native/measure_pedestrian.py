"""Source-bound pedestrian alternative observations; no legal right-of-way verdict."""
import argparse
import json
import math
from pathlib import Path

from measure_motion import measure,rows,xy,inside


def measure_pedestrian(attempt):
    attempt=Path(attempt)
    base=measure(attempt)
    context=json.loads((attempt/'traffic-context.json').read_text())
    if context.get('pedestrian_presence_reviewed') is not True or context.get('pedestrian_actor_count_at_start')!=1:
        raise ValueError('Original pedestrian presence source missing')
    actor_id=context.get('pedestrian_actor_id')
    if type(actor_id) is not int and context.get('fixture_kind')!='synthetic_diagnostic_only':
        raise ValueError('Original pedestrian actor identity missing')
    region=context['conflict_region']
    moving=[];joint=[];first_entry=None;minimum_gap=None
    for index,row in enumerate(rows(attempt/'native-motion.jsonl')):
        pedestrian=row.get('pedestrian')
        if not isinstance(pedestrian,dict):raise ValueError('Original pedestrian source missing')
        if context.get('fixture_kind')!='synthetic_diagnostic_only':
            if pedestrian.get('actor_id')!=actor_id or not str(pedestrian.get('blueprint_id','')).startswith('walker.pedestrian.'):
                raise ValueError('Original pedestrian actor classification or identity changed')
        ped,pv=xy(pedestrian);ego,ev=xy(row['ego'])
        if math.hypot(*pv)>.1:moving.append(index)
        if inside(ped,region) and first_entry is None:first_entry=index
        if ev[0]<-.1 and math.hypot(*pv)>.1:
            joint.append(index)
            gap=math.hypot(ego[0]-ped[0],ego[1]-ped[1])
            minimum_gap=gap if minimum_gap is None else min(minimum_gap,gap)
    if not moving:raise ValueError('Original pedestrian never moved')
    base.update(format='c230259-backing-pedestrian-raw-sequence-v1',
        pedestrian_moving_frame_count=len(moving),
        simultaneous_backing_and_pedestrian_motion_frame_count=len(joint),
        pedestrian_first_conflict_region_frame=first_entry,
        minimum_center_gap_during_backing_and_pedestrian_motion_m=minimum_gap)
    return base


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise ValueError('Use fresh measurement output')
    value=measure_pedestrian(args.attempt)
    args.output.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'pedestrian_moving_frame_count':value['pedestrian_moving_frame_count'],
        'simultaneous_backing_and_pedestrian_motion_frame_count':value['simultaneous_backing_and_pedestrian_motion_frame_count'],
        'right_of_way_verdict':'unresolved'}))


if __name__=='__main__':main()
