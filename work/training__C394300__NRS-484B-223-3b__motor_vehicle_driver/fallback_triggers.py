"""Evaluate fallback triggers with explicit saved-source provenance.

Synthetic diagnostics remain synthetic even when their video bytes and annotations
match. A missing or unverified annotation makes fallback3 unresolved.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from engineering import parameters


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _distance_to_polyline(point, route):
    x,y=point
    distances=[]
    for (ax,ay),(bx,by) in zip(route,route[1:]):
        dx,dy=bx-ax,by-ay
        t=max(0,min(1,((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy)))
        distances.append(math.hypot(x-(ax+t*dx),y-(ay+t*dy)))
    return min(distances)


def evaluate_native(native_samples, case_suffix, candidate_id='primary'):
    samples=_rows(native_samples)
    if not samples:
        raise ValueError('Original Native samples missing')
    synthetic=[row.get('controller_request',{}).get('synthetic_diagnostic') is True
               for row in samples]
    if any(synthetic) and not all(synthetic):
        raise ValueError('Mixed synthetic and original Native sample provenance')
    source_kind='synthetic_diagnostic' if all(synthetic) else 'original_unverified'
    prior_frame=-1;prior_time=-math.inf
    for row in samples:
        frame=row['native_frame'];time=row['time_s']
        if frame<=prior_frame or time<=prior_time:
            raise ValueError('Native frame/time sequence is not increasing')
        if len(row['native_body_xy_m'])!=4 or len(row['native_center_xy_m'])!=2:
            raise ValueError('Original body or center geometry missing')
        prior_frame=frame;prior_time=time
    initial=samples[0]['native_body_xy_m']
    initial_inside=all(1.75<y<5.25 for _,y in initial)
    # Full-body contact with the center lane is required, not a center-point crossing.
    entered_by_6s=any(row['time_s']<=6 and all(-1.75<=y<=1.75 for _,y in row['native_body_xy_m'])
                      and row['native_road_id']==1 and row['native_lane_id']==-1
                      for row in samples)
    route=parameters(case_suffix,candidate_id)['native_route_xy_m']
    # The entire requested left-turn approach is checked. A larger error signals
    # route tracking trouble; a frame-window shortcut could hide a missed turn.
    max_error=max(_distance_to_polyline(row['native_center_xy_m'],route) for row in samples)
    return {'source':'native_samples.jsonl','source_kind':source_kind,'fallback1':{
        'metric':'initial body outside adjacent through lane or no full-body center-lane entry by 6 s',
        'initial_body_inside_through_lane':initial_inside,
        'entered_center_lane_by_6s':entered_by_6s,
        'triggered':not initial_inside or not entered_by_6s},
        'fallback2':{'metric':'maximum original Native route error in attempt',
                     'max_route_error_m':max_error,'threshold_m':0.35,
                     'triggered':max_error>0.35}}


def evaluate_pixels(annotation_path, source_video_path):
    annotation=json.loads(Path(annotation_path).read_text())
    kind=annotation.get('source_kind')
    if kind not in ('synthetic_diagnostic','original_review'):
        raise ValueError('Pixel annotation source kind missing or invalid')
    source=Path(source_video_path)
    actual_sha=hashlib.sha256(source.read_bytes()).hexdigest()
    if annotation['source_video_sha256']!=actual_sha:
        raise ValueError('Pixel annotations do not bind current original source video')
    observations=annotation['approach_frames']
    if not observations or len({item['frame'] for item in observations})!=len(observations):
        raise ValueError('Approach frame annotations missing or repeated')
    if kind=='original_review' and not all(item.get('original_pixels_reviewed') is True
                                           for item in observations):
        raise ValueError('Original pixel review is absent')
    if kind=='synthetic_diagnostic' and any(item.get('original_pixels_reviewed') is not False
                                            for item in observations):
        raise ValueError('Synthetic pixels cannot be labelled original review')
    visible=sum(bool(item['body_visible'] and item['center_lane_marking_visible']) for item in observations)
    ratio=visible/len(observations)
    return {'source_kind':kind,'source_video_sha256':actual_sha,
            'reviewed_approach_frames':len(observations),
            'body_and_marking_visible_frames':visible,'visible_fraction':ratio,
            'threshold_fraction':0.95,'fallback3_triggered':ratio<0.95}


def evaluate(attempt, case_suffix, candidate_id='primary', annotation_path=None):
    attempt=Path(attempt)
    result=evaluate_native(attempt/'native_samples.jsonl',case_suffix,candidate_id)
    result['fallback3']=(evaluate_pixels(annotation_path,attempt/'approach.mkv')
                         if annotation_path is not None else
                         {'triggered':None,'reason':'independent original pixel annotations absent'})
    return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('attempt');parser.add_argument('case_suffix')
    parser.add_argument('--candidate',default='primary')
    parser.add_argument('--pixel-annotations')
    args=parser.parse_args()
    print(json.dumps(evaluate(args.attempt,args.case_suffix,args.candidate,args.pixel_annotations),indent=2))
