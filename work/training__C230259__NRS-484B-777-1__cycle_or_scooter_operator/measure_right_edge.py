"""Source-bound cyclist right-edge and standing-vehicle geometry measurement.

Geometry is evidence for review, never a definition of practicability or due care.
"""
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
VIEWS = {'overview', 'approach', 'reference_corner', 'driver_reference'}
SOURCES = ('native-cycle-frames.jsonl', 'native-map-readback.json',
           'standing-vehicle.json', 'video_frames.jsonl')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _rectangle(value, name):
    if not isinstance(value, list) or len(value) != 4 or not all(
            isinstance(point, list) and len(point) == 2 and all(_number(v) for v in point)
            for point in value):
        raise ValueError('Invalid ' + name + ' footprint')
    xs = [point[0] for point in value]
    ys = [point[1] for point in value]
    if max(xs) - min(xs) < .05 or max(ys) - min(ys) < .05:
        raise ValueError('Degenerate ' + name + ' footprint')
    return min(xs), max(xs), min(ys), max(ys)


def measure(folder, expected_hashes, diagnostic=False):
    folder = Path(folder)
    if set(expected_hashes) != set(SOURCES):
        raise ValueError('Complete saved-source hash inventory required')
    for name in SOURCES:
        if digest(folder / name) != expected_hashes[name]:
            raise ValueError('Saved source changed: ' + name)
    road = json.loads((folder / SOURCES[1]).read_text())
    standing = json.loads((folder / SOURCES[2]).read_text())
    if road.get('format') != 'c230259-road-edge-v1' or road.get('right_edge_source') not in (
            ('synthetic_cpu',) if diagnostic else ('native_map_readback',)):
        raise ValueError('Roadway right-edge source differs')
    if standing.get('format') != 'c230259-standing-vehicle-v1' or standing.get('source_kind') not in (
            ('synthetic_cpu',) if diagnostic else ('native_actor',)):
        raise ValueError('Standing-vehicle source differs')
    edge = road.get('right_roadway_edge_y_m')
    if not _number(edge) or road.get('right_side') != 'lower_y':
        raise ValueError('Calibrated right roadway edge absent')
    sx0, sx1, sy0, sy1 = _rectangle(standing.get('body_native_xy_m'), 'standing vehicle')
    if sy1 >= edge:
        raise ValueError('Standing vehicle is not outside right roadway edge')
    tracks = [json.loads(line) for line in (folder / SOURCES[0]).read_text().splitlines()]
    frames = [json.loads(line) for line in (folder / SOURCES[3]).read_text().splitlines()]
    if len(tracks) != FRAMES or len(frames) != FRAMES:
        raise ValueError('Complete 30-second frame window required')
    actor_id = None
    pass_frames = []
    margins = []
    clearances = []
    first_time = None
    for i, (track, frame) in enumerate(zip(tracks, frames)):
        if first_time is None:
            first_time = track.get('time_s')
            if not _number(first_time):
                raise ValueError('Initial Native time absent')
        if (track.get('frame') != i or frame.get('video_frame') != i or
                track.get('native_frame') != frame.get('native_frame') or
                frame.get('carla_frame') != frame.get('native_frame') or
                not _number(track.get('time_s')) or not _number(frame.get('time_s')) or
                abs(track['time_s'] - (first_time + i / 20)) > .0025 or
                abs(frame['time_s'] - track['time_s']) > .0025):
            raise ValueError('Cycle and four-camera frame join differs')
        if track.get('source_kind') not in (
                ('synthetic_native_sample',) if diagnostic else ('native_actor',)):
            raise ValueError('Cycle provenance differs')
        if actor_id is None:
            actor_id = track.get('actor_id')
        if not isinstance(actor_id, int) or track.get('actor_id') != actor_id:
            raise ValueError('Cycle actor identity differs')
        if track.get('blueprint') not in ('vehicle.bh.crossbike', 'vehicle.diamondback.century',
                                          'vehicle.gazelle.omafiets'):
            raise ValueError('Cycle identity or blueprint unsupported')
        hashes = frame.get('source_rgb_sha256')
        if not isinstance(hashes, dict) or set(hashes) != VIEWS or any(
                not isinstance(v, str) or len(v) != 64 for v in hashes.values()):
            raise ValueError('Four source-camera hashes absent')
        x0, x1, y0, y1 = _rectangle(track.get('body_native_xy_m'), 'cycle')
        if y0 < edge:
            raise ValueError('Cycle footprint crossed calibrated roadway edge')
        margins.append(y0 - edge)
        if x1 >= sx0 and x0 <= sx1:
            pass_frames.append(i)
            clearances.append(y0 - sy1)
    if not pass_frames:
        raise ValueError('Standing-vehicle passing interval absent')
    return {'format': 'c230259-right-edge-measurement-v1',
            'frames': FRAMES, 'rate_hz': 20,
            'right_edge_body_margin_min_m': round(min(margins), 5),
            'right_edge_body_margin_median_m': round(sorted(margins)[len(margins)//2], 5),
            'standing_vehicle_pass_frames': pass_frames,
            'standing_vehicle_clearance_min_m': round(min(clearances), 5),
            'source_hashes': expected_hashes,
            'source_kind': 'synthetic_diagnostic' if diagnostic else 'original_native',
            'practicability_reviewed': False, 'due_care_reviewed': False,
            'exception_status': 'unreviewed', 'legal_verdict': None}
