"""Source-bound CPU diagnostic of rail-stop position and queue arrangement."""

import hashlib
import json
import math
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(folder):
    folder = Path(folder)
    source = json.loads((folder / 'sources.json').read_text())
    if source.get('kind') not in ('synthetic_cpu_rail_stop_queue', 'native_rail_stop_queue'):
        raise ValueError('Rail source provenance differs')
    for name in ('geometry.json', 'gate.jsonl', 'actors.jsonl'):
        if digest(folder / name) != source['sha256'][name]:
            raise ValueError('Source hash differs: ' + name)
    geo = json.loads((folder / 'geometry.json').read_text())
    diagnostic = source['kind'] == 'synthetic_cpu_rail_stop_queue'
    if (set(geo) != {'rail_crossing_x_m', 'right_highway_edge_y_m',
                     'total_marked_lanes', 'vehicle_width_m', 'vehicle_length_m'}
            or geo['total_marked_lanes'] not in (2, 4, 5)
            or any(not isinstance(geo[k], (int, float)) or not math.isfinite(geo[k])
                   for k in ('rail_crossing_x_m', 'right_highway_edge_y_m',
                             'vehicle_width_m', 'vehicle_length_m'))
            or geo['vehicle_width_m'] <= 0 or geo['vehicle_length_m'] <= 0):
        raise ValueError('Rail highway geometry differs')
    if diagnostic and (geo['rail_crossing_x_m'] != 0.0
            or geo['right_highway_edge_y_m'] != {2: 3.5, 4: 7.0, 5: 8.75}[geo['total_marked_lanes']]
            or geo['vehicle_width_m'] != 1.8 or geo['vehicle_length_m'] != 4.5):
        raise ValueError('Diagnostic rail geometry differs')
    if diagnostic:
        review = None
    else:
        from source_review import reviewed_context
        review = reviewed_context(folder)
    if review and (review['total_marked_lanes'] != geo['total_marked_lanes']
                   or review['right_highway_edge_y_m'] != geo['right_highway_edge_y_m']):
        raise ValueError('Reviewed geometry differs from captured geometry')
    gate = [json.loads(x) for x in (folder / 'gate.jsonl').read_text().splitlines()]
    actors = [json.loads(x) for x in (folder / 'actors.jsonl').read_text().splitlines()]
    if len(gate) != len(actors) or len(gate) != 600:
        raise ValueError('Expected 600 Native frames per source')
    stopped_gate_frames = abreast_frames = 0
    min_right_edge_gap = None
    first_frame = gate[0]['frame']
    for i, (signal, row) in enumerate(zip(gate, actors)):
        if any(item['frame'] != first_frame + i or abs(item['time_s'] - i / 20) > 0.005
               for item in (signal, row)):
            raise ValueError('Native gate/actor frame join differs')
        if not diagnostic and (signal.get('video_frame') != i or row.get('video_frame') != i
                               or signal.get('native_actor_id') != review['gate_actor_id']
                               or row.get('camera_native_frames') is None):
            raise ValueError('Original Native frame/source join differs')
        if signal.get('kind') != 'rail_gate' or signal.get('indication') not in ('stop', 'release'):
            raise ValueError('Rail gate indication missing')
        if set(row['actors']) != {'ego', 'other'}:
            raise ValueError('Ego/other vehicle source missing')
        ego, other = row['actors']['ego'], row['actors']['other']
        if signal['indication'] == 'stop' and ego['speed_mps'] <= 0.1 and other['speed_mps'] <= 0.1:
            stopped_gate_frames += 1
            rightmost = ego.get('footprint_m', {}).get('max_y') if not diagnostic else None
            right_gap = geo['right_highway_edge_y_m'] - (rightmost if rightmost is not None else ego['y_m'] + geo['vehicle_width_m'] / 2)
            min_right_edge_gap = right_gap if min_right_edge_gap is None else min(min_right_edge_gap, right_gap)
            if not diagnostic:
                a, b = ego['footprint_m'], other['footprint_m']
                longitudinal_overlap = min(a['max_x'], b['max_x']) > max(a['min_x'], b['min_x'])
                lateral_separate = a['max_y'] < b['min_y'] or b['max_y'] < a['min_y']
            else:
                longitudinal_overlap = abs(ego['x_m'] - other['x_m']) < geo['vehicle_length_m']
                lateral_separate = abs(ego['y_m'] - other['y_m']) >= geo['vehicle_width_m']
            abreast_frames += longitudinal_overlap and lateral_separate
    return {'source_kind': source['kind'], 'source_sha256': source['sha256'],
            'frame_count': 600, 'rate_hz': 20, 'stopped_during_gate_stop_frames': stopped_gate_frames,
            'minimum_right_edge_gap_m': round(min_right_edge_gap, 6) if min_right_edge_gap is not None else None,
            'abreast_two_queue_frames': abreast_frames, 'total_marked_lanes': geo['total_marked_lanes'],
            'stopping_requirement_authority_verified': bool(review), 'rightmost_possible_judgment': 'unresolved',
            'two_lanes_legal_judgment': 'unresolved', 'physical_native_verified': bool(review),
            'legal_verdict_claimed': False}
