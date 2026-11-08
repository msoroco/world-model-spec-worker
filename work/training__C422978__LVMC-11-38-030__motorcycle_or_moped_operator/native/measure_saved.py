"""Measure original Native motorcycle body occupancy of the surveyed sidewalk.

No city-context or statutory verdict is inferred from authored OpenDRIVE alone.
"""
import hashlib
import json
import math
from pathlib import Path

SOURCES = ('native-observed.jsonl', 'native-map-readback.json',
           'video_frames.jsonl', 'capture/evidence.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(folder, name):
    path = Path(folder) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def measure(folder):
    folder = Path(folder)
    for name in SOURCES: source(folder, name)
    observed = rows(source(folder, 'native-observed.jsonl'))
    mapping = rows(source(folder, 'video_frames.jsonl'))
    evidence = rows(source(folder, 'capture/evidence.jsonl'))
    survey = json.loads(source(folder, 'native-map-readback.json').read_text())
    if (survey.get('sidewalk_road_id') != 1 or survey.get('sidewalk_lane_id') != -2 or
            survey.get('motorcycle_blueprint') != 'vehicle.kawasaki.ninja'):
        raise ValueError('Native sidewalk or motorcycle readback differs')
    if any(len(group) != 480 for group in (observed, mapping, evidence)):
        raise ValueError('Original saved frame count differs')
    kinds = {row.get('source_kind') for row in observed}
    if len(kinds) != 1 or kinds.pop() not in ('synthetic_cpu', 'original_native'):
        raise ValueError('Saved provenance differs')
    overlap, full_inside, moving, lane_readback = [], [], [], []
    prior_native = None
    for index, (row, video, captured) in enumerate(zip(observed, mapping, evidence)):
        frame = row.get('native_frame')
        time = float(row.get('time_s', -1))
        if (row.get('frame') != index or type(frame) is not int or
                (prior_native is not None and frame != prior_native + 1) or
                video.get('video_frame') != index or video.get('native_frame') != frame or
                video.get('carla_frame') != frame or
                captured.get('original_frame') != frame or
                abs(float(video.get('time_s', -2)) - time) > 1e-4 or
                abs(float(captured.get('recording_time_s', -3)) - time) > 1e-4):
            raise ValueError('Original Native/video/capture frame join differs')
        prior_native = frame
        if row.get('motorcycle_blueprint') != 'vehicle.kawasaki.ninja':
            raise ValueError('Original motorcycle identity differs')
        center, body = row.get('center_native_xy_m'), row.get('body_native_xy_m')
        if not isinstance(center, list) or len(center) != 2 or not isinstance(body, list) or len(body) != 4:
            raise ValueError('Original motorcycle body absent')
        points = [(float(p[0]), float(p[1])) for p in body]
        if (len(set(points)) != 4 or
                not all(math.isfinite(v) for point in points for v in point) or
                abs(sum(p[0] for p in points)/4 - float(center[0])) > .1 or
                abs(sum(p[1] for p in points)/4 - float(center[1])) > .1):
            raise ValueError('Original motorcycle body/center differs')
        speed = float(row.get('speed_mps', -1))
        if not math.isfinite(speed) or speed < 0:
            raise ValueError('Original motorcycle speed invalid')
        ys = [p[1] for p in points]
        is_moving = speed > .1
        if is_moving: moving.append(index)
        if is_moving and min(ys) < 5.5 and max(ys) > 3.5:
            overlap.append(index)
        if is_moving and min(ys) >= 3.5 and max(ys) <= 5.5:
            full_inside.append(index)
        if row.get('native_lane_id') == -2: lane_readback.append(index)
    contiguous, longest, previous = 0, 0, -2
    for index in overlap:
        contiguous = contiguous + 1 if index == previous + 1 else 1
        longest = max(longest, contiguous)
        previous = index
    return {'format': 'c422978-sidewalk-saved-occupancy-v1',
            'source_kind': observed[0]['source_kind'],
            'frames': 480, 'moving_frames': len(moving),
            'moving_sidewalk_overlap_frames': len(overlap),
            'first_moving_sidewalk_overlap_frame': overlap[0] if overlap else None,
            'longest_moving_sidewalk_overlap_frames': longest,
            'full_body_inside_sidewalk_frames': len(full_inside),
            'native_sidewalk_lane_readback_frames': len(lane_readback),
            'city_sidewalk_verified': bool(survey.get('city_location_verified')),
            'legal_verdict': None,
            'source_hashes': {name: sha(source(folder, name)) for name in SOURCES}}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('folder')
    args = parser.parse_args()
    print(json.dumps(measure(args.folder), indent=2))
