"""Review original person and vehicle pixels at the statutory 1,000-foot reference."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


DISTANCE_M = 304.8
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def measure(trace_raw, map_raw, review_raw, context_raw, frame_map_raw):
    context = json.loads(context_raw)
    kind = context.get('source_kind')
    require(kind in ('native_saved_sample', 'synthetic_diagnostic'),
            'Original Native or explicit synthetic visibility source required')
    require(context.get('map_source_sha256') == sha(map_raw),
            'Visibility map source changed')
    requested_ft = context.get('requested_boundary_distance_ft', 1000)
    require(requested_ft in (999, 1000, 1001),
            'Visibility boundary probe outside 1,000-foot neighborhood')
    reference_m = requested_ft * .3048
    require(abs(context.get('reference_distance_m', -1) - reference_m) < 1e-8 and
            context.get('statutory_reference_distance_m', DISTANCE_M) == DISTANCE_M,
            'Statutory or requested visibility reference changed')
    rows = [json.loads(line) for line in trace_raw.splitlines() if line.strip()]
    frame_rows = [json.loads(line) for line in frame_map_raw.splitlines() if line.strip()]
    require(len(rows) == 600, 'Visibility trace must cover 600 original frames')
    require(len(frame_rows) == len(rows), 'Visibility frame map length changed')
    person_rows, vehicle_rows = [], []
    previous = None
    for index, row in enumerate(rows):
        require(row.get('video_frame') == index and
                isinstance(row.get('native_frame'), int) and
                (previous is None or row['native_frame'] > previous),
                'Visibility frames are missing or out of order')
        previous = row['native_frame']
        require(row.get('camera_native_frames') ==
                {name: previous for name in CAMERAS},
                'Visibility camera source join missing')
        require(frame_rows[index].get('video_frame') == index and
                frame_rows[index].get('native_frame') == previous and
                frame_rows[index].get('camera_native_frames') ==
                row['camera_native_frames'],
                'Original visibility frame map differs')
        for key, found in (('person_forward_distance_m', person_rows),
                           ('vehicle_forward_distance_m', vehicle_rows)):
            value = row.get(key)
            require(type(value) in (int, float), 'Original target distance missing')
            if abs(value - reference_m) <= .15:
                found.append(index)
    require(set(person_rows) & set(vehicle_rows),
            'No source frame places both targets at 1,000 feet')
    review = json.loads(review_raw)
    require(review.get('source_kind') == ('original_pixel_review' if
            kind == 'native_saved_sample' else 'synthetic_diagnostic') and
            review.get('trace_sha256') == sha(trace_raw) and
            review.get('context_sha256') == sha(context_raw) and
            review.get('map_sha256') == sha(map_raw) and
            review.get('frame_map_sha256') == sha(frame_map_raw),
            'Independent original visibility review missing or stale')
    require(review.get('reviewer_id') and review.get('person_video_sha256') and
            review.get('vehicle_video_sha256'),
            'Original camera source identity missing')
    require(set(review.get('person_review_frames', [])) <= set(person_rows) and
            set(review.get('vehicle_review_frames', [])) <= set(vehicle_rows) and
            review.get('person_review_frames') and review.get('vehicle_review_frames'),
            'Reviewed frames do not show exact-distance sources')
    for key in ('person_clearly_discernible', 'vehicle_clearly_discernible'):
        require(type(review.get(key)) is bool,
                'Independent person and vehicle pixel findings required')
    return {'format': 'c179824-visibility-measurement-v1',
            'source_kind': kind,
            'reference_distance_m': reference_m,
            'statutory_reference_distance_m': DISTANCE_M,
            'requested_boundary_distance_ft': requested_ft,
            'person_source_frames': person_rows,
            'vehicle_source_frames': vehicle_rows,
            'person_clearly_discernible': review['person_clearly_discernible'],
            'vehicle_clearly_discernible': review['vehicle_clearly_discernible'],
            'source_hashes': {'trace': sha(trace_raw), 'map': sha(map_raw),
                              'frame_map': sha(frame_map_raw),
                              'context': sha(context_raw), 'review': sha(review_raw)},
            'legal_verdict_claimed': False}


def self_test(negative=False):
    road = b'<OpenDRIVE/>'
    frames = b''.join(json.dumps({'video_frame': i, 'native_frame': 1000+i,
        'camera_native_frames': {name: 1000+i for name in CAMERAS}},
        separators=(',', ':')).encode()+b'\n' for i in range(600))
    outcomes = {}
    for requested_ft in (999, 1000, 1001):
        target_m = requested_ft * .3048
        context = json.dumps({'source_kind': 'native_saved_sample',
                              'map_source_sha256': sha(road),
                              'reference_distance_m': target_m,
                              'statutory_reference_distance_m': DISTANCE_M,
                              'requested_boundary_distance_ft': requested_ft}).encode()
        trace = b''.join(json.dumps({'video_frame': i, 'native_frame': 1000+i,
            'camera_native_frames': {name: 1000+i for name in CAMERAS},
            'person_forward_distance_m': target_m if i == 0 else target_m-i*.1,
            'vehicle_forward_distance_m': target_m if i == 0 else target_m-i*.1},
            separators=(',', ':')).encode()+b'\n' for i in range(600))
        review = {'source_kind': 'original_pixel_review',
                  'reviewer_id': 'cpu-predicate-fixture',
                  'trace_sha256': sha(trace), 'map_sha256': sha(road),
                  'context_sha256': sha(context), 'frame_map_sha256': sha(frames),
                  'person_video_sha256': sha(b'person'),
                  'vehicle_video_sha256': sha(b'vehicle'),
                  'person_review_frames': [0], 'vehicle_review_frames': [0],
                  'person_clearly_discernible': True,
                  'vehicle_clearly_discernible': False}
        if negative:
            review.pop('person_video_sha256')
            return measure(trace, road, json.dumps(review).encode(), context, frames)
        measured = measure(trace, road, json.dumps(review).encode(), context, frames)
        require(measured['requested_boundary_distance_ft'] == requested_ft,
                'Visibility boundary reference changed')
        outcomes[str(requested_ft)] = {'distance_m': measured['reference_distance_m'],
                                        'joint_reference_frames': len(set(measured['person_source_frames']) &
                                                                      set(measured['vehicle_source_frames']))}
    return {'format': 'c179824-visibility-boundary-cpu-proof-v1',
            'diagnostic_fixture': True, 'probes': outcomes,
            'original_capture_attested': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--attempt')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(args.negative), indent=2))
    else:
        require(args.attempt and args.output, 'Saved attempt and output required')
        root = Path(args.attempt)
        trace = (root/'visibility-trace.jsonl').read_bytes()
        road = (root/'road.xodr').read_bytes()
        review = (root/'visibility-pixel-review.json').read_bytes()
        context = (root/'visibility-context.json').read_bytes()
        frame_map = (root/'video_frames.jsonl').read_bytes()
        review_data = json.loads(review)
        for role in ('person', 'vehicle'):
            name = review_data.get(role+'_video')
            require(name in [camera+'.mkv' for camera in CAMERAS],
                    'Original '+role+' review camera missing')
            require(sha((root/name).read_bytes()) == review_data.get(role+'_video_sha256'),
                    'Original '+role+' video hash changed')
        result = measure(trace, road, review, context, frame_map)
        Path(args.output).write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result, sort_keys=True))
