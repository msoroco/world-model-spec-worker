"""Evaluate the C228133 walker-path fallback from retained source rows.

This decides only whether an engineering retry is indicated. It does not
decide the statutory predicate or choose a case by desired legal outcome.
"""
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
RATE_HZ = 20


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evaluate(folder, expected_hashes, requested_speed_mps, diagnostic=False):
    folder = Path(folder)
    names = ('native-pedestrian-frames.jsonl', 'video_frames.jsonl',
             'road-boundary.json')
    if set(expected_hashes) != set(names):
        raise ValueError('Complete source-hash inventory required')
    for name in names:
        if digest(folder / name) != expected_hashes[name]:
            raise ValueError('Retained fallback source changed: ' + name)
    if type(requested_speed_mps) not in (int, float) or not math.isfinite(requested_speed_mps) or requested_speed_mps <= 0:
        raise ValueError('Requested walker speed invalid')
    boundary = json.loads((folder / 'road-boundary.json').read_text())
    if boundary.get('format') != 'pedestrian-road-boundary-v1' or boundary.get('road_side') not in ('at_or_above_y', 'at_or_below_y'):
        raise ValueError('Calibrated road side absent')
    footprints = [json.loads(row) for row in (folder / names[0]).read_text().splitlines()]
    frames = [json.loads(row) for row in (folder / names[1]).read_text().splitlines()]
    if len(footprints) != FRAMES or len(frames) != FRAMES:
        raise ValueError('Full 30-second source window required')
    jump_frames = []
    previous = None
    actor_id = None
    first_time = None
    for index, (footprint, frame) in enumerate(zip(footprints, frames)):
        kind = footprint.get('source_kind')
        if kind not in (('synthetic_native_sample',) if diagnostic else ('native_actor',)):
            raise ValueError('Footprint provenance differs')
        if first_time is None:
            first_time = footprint.get('time_s')
            if type(first_time) not in (int, float) or not math.isfinite(first_time):
                raise ValueError('First Native timestamp invalid')
        expected_time = first_time + index / RATE_HZ
        if (footprint.get('frame') != index or frame.get('video_frame') != index or
                footprint.get('native_frame') != frame.get('native_frame') or
                frame.get('carla_frame') != frame.get('native_frame') or
                abs(footprint.get('time_s', -1) - expected_time) > .0025 or
                abs(frame.get('time_s', -1) - expected_time) > .0025):
            raise ValueError('Pedestrian and four-camera frame join differs')
        hashes = frame.get('source_rgb_sha256')
        if not isinstance(hashes, dict) or set(hashes) != {
                'overview', 'approach', 'reference_corner', 'driver_reference'} or any(
                    not isinstance(value, str) or len(value) != 64 for value in hashes.values()):
            raise ValueError('Four original camera hashes absent')
        if actor_id is None:
            actor_id = footprint.get('actor_id')
        if footprint.get('actor_id') != actor_id or not isinstance(actor_id, int):
            raise ValueError('Walker actor identity differs')
        y = footprint.get('footprint_roadward_y_m')
        if type(y) not in (int, float) or not math.isfinite(y):
            raise ValueError('Walker footprint invalid')
        if previous is not None and abs(y - previous) > 2 * requested_speed_mps / RATE_HZ + .02:
            jump_frames.append(index)
        previous = y
    return {'format': 'c228133-fallback2-path-trigger-v1',
            'source_hashes': expected_hashes,
            'requested_speed_mps': requested_speed_mps,
            'max_step_m': 2 * requested_speed_mps / RATE_HZ + .02,
            'unstable_step_frames': jump_frames,
            'fallback2_triggered': bool(jump_frames),
            'source_kind': 'synthetic_diagnostic' if diagnostic else 'original_native',
            'legal_verdict': None, 'physical_acceptance': False}
