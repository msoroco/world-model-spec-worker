"""Source-bound stopped/parked branch observation for NRS 484D.100(1)."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def measure(trace_raw, review_raw):
    rows = [json.loads(line) for line in trace_raw.splitlines() if line.strip()]
    require(len(rows) == 600, 'Original parked-branch trace needs 600 frames')
    kind = rows[0].get('source_kind') if rows else None
    require(kind in ('native_saved_sample', 'synthetic_diagnostic'),
            'Parked source kind missing')
    require(all(row.get('source_kind') == kind and
                row.get('video_frame') == i and
                type(row.get('speed_mps')) in (int, float) and
                row.get('road_id') for i, row in enumerate(rows)),
            'Original parked-branch motion or highway source missing')
    parked = [i for i, row in enumerate(rows) if row['speed_mps'] <= .1]
    require(len(parked) >= 100 and parked[-100:] == list(range(500, 600)),
            'Parked/stopped phase not sustained in final 100 frames')
    review = json.loads(review_raw)
    expected_review = ('independent_original_review' if kind == 'native_saved_sample'
                       else 'synthetic_diagnostic')
    require(review.get('source_kind') == expected_review and
            review.get('trace_sha256') == sha(trace_raw) and
            review.get('reviewer_id') and
            review.get('highway_and_shoulder_source_sha256') and
            review.get('parked_status_source_sha256') and
            review.get('nrs_484d_165_source_sha256') and
            review.get('pixel_video_sha256'),
            'Original parked exception source review missing or stale')
    for field in ('on_traveled_portion_or_adjacent_shoulder',
                  'insufficient_light_at_1000ft',
                  'front_lamp_visible_at_500ft',
                  'rear_lamp_visible_at_500ft',
                  'lamp_near_traffic_side', 'headlamp_dimmed_if_lit'):
        require(type(review.get(field)) is bool,
                'Original parked exception finding missing: '+field)
    return {'format': 'c179824-parked-exception-measurement-v1',
            'source_kind': kind,
            'parked_final_frames': len(parked[-100:]),
            'observed': {field: review[field] for field in
                         ('on_traveled_portion_or_adjacent_shoulder',
                          'insufficient_light_at_1000ft',
                          'front_lamp_visible_at_500ft',
                          'rear_lamp_visible_at_500ft',
                          'lamp_near_traffic_side', 'headlamp_dimmed_if_lit')},
            'trace_sha256': sha(trace_raw), 'review_sha256': sha(review_raw),
            'legal_verdict_claimed': False}


def self_test(negative=False):
    trace = b''.join(json.dumps({'source_kind': 'native_saved_sample',
        'video_frame': i, 'speed_mps': 2.8 if i < 450 else 0.0,
        'road_id': '1'}, separators=(',', ':')).encode()+b'\n'
        for i in range(600))
    review = {'source_kind': 'independent_original_review',
              'trace_sha256': sha(trace), 'reviewer_id': 'cpu-predicate-fixture',
              'highway_and_shoulder_source_sha256': sha(b'highway'),
              'parked_status_source_sha256': sha(b'parked'),
              'nrs_484d_165_source_sha256': sha(b'NRS 484D.165'),
              'pixel_video_sha256': sha(b'video'),
              'on_traveled_portion_or_adjacent_shoulder': True,
              'insufficient_light_at_1000ft': True,
              'front_lamp_visible_at_500ft': True,
              'rear_lamp_visible_at_500ft': True,
              'lamp_near_traffic_side': True,
              'headlamp_dimmed_if_lit': True}
    if negative:
        review.pop('parked_status_source_sha256')
    return measure(trace, json.dumps(review).encode())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--trace')
    parser.add_argument('--review')
    parser.add_argument('--source-root')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(args.negative), indent=2))
    else:
        require(args.trace and args.review and args.output and args.source_root,
                'Original trace, parked review, sources and output required')
        root = Path(args.source_root).resolve()
        review_raw = Path(args.review).read_bytes()
        review = json.loads(review_raw)
        for field in ('highway_and_shoulder', 'parked_status',
                      'nrs_484d_165', 'pixel_video'):
            rel = review.get(field+'_path')
            require(isinstance(rel, str) and rel and not Path(rel).is_absolute(),
                    'Original parked branch source path missing: '+field)
            path = (root/rel).resolve()
            key = 'pixel_video_sha256' if field == 'pixel_video' else field+'_source_sha256'
            require(root in path.parents and path.is_file() and
                    sha(path.read_bytes()) == review.get(key),
                    'Original parked branch source changed: '+field)
        result = measure(Path(args.trace).read_bytes(), review_raw)
        Path(args.output).write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result, sort_keys=True))
