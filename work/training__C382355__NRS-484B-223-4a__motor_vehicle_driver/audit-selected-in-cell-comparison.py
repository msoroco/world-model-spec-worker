"""Independent CPU comparison of the two selected right-turn source fixtures."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):return [json.loads(line) for line in path.read_text().splitlines()]


def audit():
    roots=[HERE/'selected-source'/name for name in ('controlled_1','controlled_2')]
    traces=[rows(root/'trace.jsonl') for root in roots]
    samples=[rows(root/'native_samples.jsonl') for root in roots]
    maps=[rows(root/'video_frames.jsonl') for root in roots]
    if any(len(x)!=480 for group in (traces,samples,maps) for x in group):
        raise ValueError('Selected source frame count differs')
    if (sha(roots[0]/'road.xodr')!=sha(roots[1]/'road.xodr') or
            sha(roots[0]/'video_frames.jsonl')!=sha(roots[1]/'video_frames.jsonl')):
        raise ValueError('Selected map or frame timing differs')
    for index in range(480):
        for run in range(2):
            if traces[run][index]['frame']!=maps[run][index]['native_frame'] or \
                    samples[run][index]['native_frame']!=maps[run][index]['native_frame']:
                raise ValueError('Original source join differs')
    first=[row for row in samples[0] if row['native_road_id']==1 and row['native_center_xy_m'][0]<-10]
    second=[row for row in samples[1] if row['native_road_id']==1 and row['native_center_xy_m'][0]<-10]
    if not first or not second or {row['native_lane_id'] for row in first}!={-2} or \
            {row['native_lane_id'] for row in second}!={-1}:
        raise ValueError('Approach lane variable not isolated')
    if any(run[-1]['native_road_id']!=4 or run[-1]['native_forward_xy'][1]<.95 for run in samples):
        raise ValueError('Both selected cases must complete a right turn')
    return {'passed':True,'cases':['controlled_1','controlled_2'],
            'variable':'measured approach occupancy of the single right-only lane',
            'approach_lane_ids':[-2,-1], 'exit_road_ids':[4,4],
            'fixed_map_sha256':sha(roots[0]/'road.xodr'),
            'fixed_frame_map_sha256':sha(roots[0]/'video_frames.jsonl'),
            'native_executed':False,'physical_acceptance_claimed':False,
            'source_hashes':{name:{p.name:sha(p) for p in (root/'trace.jsonl',root/'native_samples.jsonl')}
                             for name,root in zip(('controlled_1','controlled_2'),roots)}}


if __name__=='__main__':print(json.dumps(audit(),indent=2))
