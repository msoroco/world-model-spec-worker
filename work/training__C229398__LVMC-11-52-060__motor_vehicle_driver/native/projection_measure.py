"""Measure the full vehicle, load and trailer extent normal to a source curb.

This computes a geometric observation from retained vertices. It makes no
claim that a CPU fixture is original Native capture or a legal finding.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

FEET_PER_METER = 3.280839895013123
PARTS = ('vehicle', 'load', 'trailer')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def point(value):
    if not isinstance(value, list) or len(value) != 2 or not all(
            isinstance(v, (float, int)) and math.isfinite(v) for v in value):
        raise ValueError('Expected finite 2D source point')
    return tuple(float(v) for v in value)


def measure(curb_path, footprint_path, required_frames=600, allow_synthetic=False):
    curb_path = Path(curb_path)
    footprint_path = Path(footprint_path)
    curb = json.loads(curb_path.read_text())
    if curb.get('format') != 'c229398-reviewed-curb-v1':
        raise ValueError('Curb review format missing')
    source_kind = 'synthetic_native_sample' if allow_synthetic else 'native'
    if curb.get('reviewed') is not True or curb.get('source_kind') != source_kind:
        raise ValueError('Original curb source review required')
    if not isinstance(curb.get('source_sha256'), str) or len(curb['source_sha256']) != 64:
        raise ValueError('Curb source hash missing')
    source_file = curb.get('source_file')
    if not isinstance(source_file, str) or Path(source_file).name != source_file:
        raise ValueError('Curb source file missing')
    source_path = curb_path.parent / source_file
    if not source_path.is_file() or sha(source_path) != curb['source_sha256']:
        raise ValueError('Curb source bytes changed')
    origin = point(curb['origin_xy_m'])
    normal = point(curb['street_normal_xy'])
    if abs(math.hypot(*normal) - 1.0) > 1e-6:
        raise ValueError('Street normal must be unit length')
    if type(required_frames) is not int or required_frames < 600:
        raise ValueError('At least 30 seconds at 20 Hz required')
    rows = [json.loads(line) for line in footprint_path.read_text().splitlines()
            if line.strip()]
    if len(rows) != required_frames:
        raise ValueError('Missing or extra footprint frame')
    extrema = []
    for frame, row in enumerate(rows):
        if row.get('frame') != frame or row.get('source_kind') != source_kind:
            raise ValueError('Native frame/source identity mismatch')
        if row.get('curb_sha256') != sha(curb_path):
            raise ValueError('Curb calibration changed')
        participants = row.get('participants')
        if not isinstance(participants, dict) or set(participants) != set(PARTS):
            raise ValueError('Vehicle, load and trailer inventories required')
        frame_max = None
        for part in PARTS:
            item = participants[part]
            if item is None:
                if part == 'vehicle':
                    raise ValueError('Vehicle footprint missing')
                continue
            vertices = item.get('vertices_xy_m') if isinstance(item, dict) else None
            if not isinstance(vertices, list) or len(vertices) < 3:
                raise ValueError('Source footprint vertices missing: ' + part)
            for vertex in vertices:
                x, y = point(vertex)
                projection = ((x - origin[0]) * normal[0] +
                              (y - origin[1]) * normal[1])
                frame_max = projection if frame_max is None else max(frame_max, projection)
        extrema.append(frame_max)
    maximum_m = max(extrema)
    maximum_ft = max(0.0, maximum_m) * FEET_PER_METER
    return {'format': 'c229398-curb-projection-measurement-v1',
            'frames': required_frames, 'fps': 20,
            'duration_seconds': required_frames / 20,
            'maximum_projection_perpendicular_to_curb_m': maximum_m,
            'maximum_projection_perpendicular_to_curb_ft': maximum_ft,
            'curb_sha256': sha(curb_path), 'footprints_sha256': sha(footprint_path),
            'source_kind': source_kind, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--curb', required=True)
    parser.add_argument('--footprints', required=True)
    parser.add_argument('--frames', type=int, default=600)
    parser.add_argument('--allow-synthetic', action='store_true')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(measure(args.curb, args.footprints,
                                                    args.frames, args.allow_synthetic),
                                             indent=2) + '\n')
