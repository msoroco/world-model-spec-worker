"""Independent raw-source audit of an engineering distance triple.

The body-edge gap is diagnostic. This audit never chooses the legal reference
point or asserts that a synthetic outline is an actual fire-station entrance.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def observe(folder, side):
    folder = Path(folder)
    context = json.loads((folder / 'entrance-context.json').read_text())
    kind = context.get('source_kind')
    if kind not in ('synthetic_diagnostic', 'original_native'):
        raise ValueError('Unidentified entrance source')
    if context.get('initial_activity') != 'parked' or context.get('exception_context') != 'none':
        raise ValueError('Activity or exception differs')
    if kind == 'original_native':
        authority = folder / 'authority/manifest.json'
        if not authority.is_file() or digest(authority) != context.get('authority_manifest_sha256'):
            raise ValueError('Original authority manifest missing or changed')
        for name, expected in (context.get('authority_source_sha256') or {}).items():
            source = folder / 'authority' / (name + '.source')
            if not source.is_file() or digest(source) != expected:
                raise ValueError('Original authority source missing or changed: ' + name)
    motion = [json.loads(line) for line in (folder / 'native-vehicle.jsonl').read_text().splitlines()]
    frames = [json.loads(line) for line in (folder / 'video_frames.jsonl').read_text().splitlines()]
    if len(motion) != 600 or len(frames) != 600:
        raise ValueError('Motion or frame map incomplete')
    gaps = []
    entrance = context['entrance']
    for i, (row, frame) in enumerate(zip(motion, frames)):
        if row.get('video_frame') != i or frame.get('video_frame') != i or row.get('native_frame') != frame.get('native_frame'):
            raise ValueError('Original frame join differs')
        if row.get('time_s') != i / 20 or frame.get('time_s') != i / 20:
            raise ValueError('Original timing differs')
        if row.get('source_kind') != kind:
            raise ValueError('Motion provenance differs')
        if i < 500:
            continue
        if row.get('speed_mps', 999) > .1:
            raise ValueError('Sustained rest missing')
        center = row.get('center_xy_m')
        if not isinstance(center, list) or len(center) != 2 or (center[1] < 0) != (side == 'same'):
            raise ValueError('Wrong highway side')
        body = row.get('body_xy_m')
        if not isinstance(body, list) or len(body) < 4:
            raise ValueError('Vehicle body corners missing')
        xs = [point[0] for point in body]
        if any(type(x) not in (int, float) or not math.isfinite(x) for x in xs):
            raise ValueError('Invalid body corner')
        gaps.append(max(0, entrance['x_min_m'] - max(xs), min(xs) - entrance['x_max_m']))
    return context, motion, min(gaps), digest(folder / 'native-vehicle.jsonl')


def compare(far, at, near, side):
    if side not in ('same', 'opposite'):
        raise ValueError('Unknown highway side')
    folders = [Path(path) for path in (far, at, near)]
    for name in ('road.xodr', 'video_frames.jsonl', 'acquisition-provenance.json'):
        hashes = [digest(folder / name) for folder in folders]
        if len(set(hashes)) != 1:
            raise ValueError('Fixed source differs: ' + name)
    observed = [observe(folder, side) for folder in folders]
    contexts = [item[0] for item in observed]
    if any(context != contexts[0] for context in contexts[1:]):
        raise ValueError('Fixed entrance context differs')
    for rows in zip(*(item[1] for item in observed)):
        for key in ('native_frame', 'video_frame', 'time_s', 'actor_id', 'blueprint_id'):
            if len({json.dumps(row.get(key), sort_keys=True) for row in rows}) != 1:
                raise ValueError('Fixed actor or timing differs: ' + key)
    far_gap, at_gap, near_gap = [item[2] for item in observed]
    target = 6.096 if side == 'same' else 22.86
    if not (far_gap > target > near_gap and math.isclose(at_gap, target, abs_tol=1e-6)):
        raise ValueError('Engineering below/at/above triple absent')
    return {'format': 'c229410-threshold-source-comparison-v1', 'passed': True,
            'source_kind': contexts[0]['source_kind'], 'side': side,
            'raw_body_edge_gaps_m': [far_gap, at_gap, near_gap],
            'motion_sha256': [item[3] for item in observed],
            'statutory_reference_method_adopted': False,
            'physical_or_legal_result_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--far', required=True)
    parser.add_argument('--at', required=True)
    parser.add_argument('--near', required=True)
    parser.add_argument('--side', choices=('same', 'opposite'), required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.far, args.at, args.near, args.side), sort_keys=True))
