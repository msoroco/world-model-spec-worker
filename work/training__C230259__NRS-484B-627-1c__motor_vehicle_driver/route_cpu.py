"""Saved-route diagnostic for NRS 484B.627(1)(c).

The generated tracks are synthetic CPU requests. The reducer checks a full
exit opportunity and a connected route, but makes no legal or Native claim.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
FRAMES = 600
HZ = 20
EXIT_X_M = 90.0


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def graph():
    return {'source_kind': 'synthetic_cpu', 'controlled_access': True,
            'highway_road_id': 'hwy', 'exit_x_m': EXIT_X_M,
            'edges': [['hwy_before', 'hwy_after'], ['hwy_before', 'exit'],
                      ['exit', 'alternate'], ['alternate', 'destination'],
                      ['hwy_after', 'destination']],
            'start': 'hwy_before', 'destination': 'destination',
            'alternate_exit': 'exit', 'alternate_route': 'alternate',
            'designation_independently_verified': False,
            'exit_usability_physically_verified': False}


def track(take_exit):
    result = []
    for i in range(FRAMES):
        t = i / HZ
        x = 5 * t
        y = 0.0 if not take_exit or x < EXIT_X_M else min(8.0, (x - EXIT_X_M) / 3)
        route = 'alternate' if take_exit and y >= 8 else ('exit' if take_exit and x >= EXIT_X_M else 'hwy')
        result.append({'frame': i, 'time_s': t, 'source_kind': 'synthetic_cpu',
                       'ego': {'id': 'ego', 'x_m': x, 'y_m': y, 'speed_mps': 5.0,
                               'road': route},
                       'behind': [{'id': 'following-1', 'x_m': x - 12.0,
                                   'y_m': 0.0, 'speed_mps': 8.0},
                                  {'id': 'following-2', 'x_m': x - 28.0,
                                   'y_m': 0.0, 'speed_mps': 8.0}]})
    return result


def reachable(edges, start, destination):
    pending = [start]
    visited = set()
    while pending:
        node = pending.pop()
        if node == destination:
            return True
        if node in visited:
            continue
        visited.add(node)
        pending.extend(v for u, v in edges if u == node)
    return False


def measure(track_bytes, graph_bytes, envelope_bytes):
    envelope = json.loads(envelope_bytes)
    require(envelope.get('assignment_id') == ASSIGNMENT, 'assignment differs')
    require(envelope.get('track_sha256') == digest(track_bytes)
            and envelope.get('graph_sha256') == digest(graph_bytes),
            'source hash differs')
    require(envelope.get('source_kind') == 'synthetic_cpu', 'source type differs')
    rows = [json.loads(line) for line in track_bytes.splitlines() if line]
    road = json.loads(graph_bytes)
    require(road.get('source_kind') == 'synthetic_cpu'
            and road.get('controlled_access') is True
            and road.get('highway_road_id') == 'hwy',
            'controlled-access source context missing')
    edges = road.get('edges')
    require(isinstance(edges, list) and all(isinstance(e, list) and len(e) == 2 for e in edges),
            'route topology missing')
    require(['hwy_before', 'exit'] in edges
            and reachable(edges, road['alternate_exit'], road['destination'])
            and ['exit', road['alternate_route']] in edges,
            'connected alternate route missing')
    require(len(rows) == FRAMES, 'full exit-window trace missing')
    prev_x = -math.inf
    encountered_exit = False
    queue_frames = 0
    exit_frames = []
    for i, row in enumerate(rows):
        require(row.get('frame') == i and row.get('time_s') == i / HZ
                and row.get('source_kind') == 'synthetic_cpu',
                'time/source join differs')
        ego = row.get('ego', {})
        x, speed = ego.get('x_m'), ego.get('speed_mps')
        require(all(type(v) in (int, float) and math.isfinite(v) for v in (x, speed))
                and x >= prev_x and ego.get('id') == 'ego',
                'ego motion source differs')
        prev_x = x
        if x >= road['exit_x_m']:
            encountered_exit = True
            exit_frames.append(i)
        followers = row.get('behind')
        require(isinstance(followers, list) and len(followers) == 2,
                'immediately behind traffic source missing')
        gaps = []
        for vehicle in followers:
            gap = x - vehicle['x_m']
            require(0 < gap < 50 and vehicle['speed_mps'] > speed
                    and vehicle['y_m'] == 0 and vehicle.get('id'),
                    'following movement source differs')
            gaps.append(gap)
        require(gaps[0] < gaps[1], 'immediate follower order differs')
        queue_frames += 1
    require(encountered_exit and exit_frames[-1] - exit_frames[0] >= 80,
            'usable exit observation window missing')
    departure = next((r['frame'] for r in rows if r['ego']['road'] == 'alternate'), None)
    if departure is not None:
        require(departure in exit_frames and all(r['ego']['road'] != 'hwy' for r in rows[departure:]),
                'alternate-route trace differs')
    else:
        require(all(r['ego']['road'] == 'hwy' for r in rows), 'unmeasured route transition')
    return {'format': 'c230259-route-cpu-facts-v1', 'track_sha256': digest(track_bytes),
            'graph_sha256': digest(graph_bytes), 'frame_count': FRAMES,
            'duration_s': FRAMES / HZ, 'follower_pair_frames': queue_frames,
            'exit_observation_frames': len(exit_frames),
            'alternate_route_connected_in_authored_graph': True,
            'alternate_route_departure_frame': departure,
            'original_native_observed': False, 'controlled_access_independently_verified': False,
            'impeding_legally_determined': False, 'legal_result': None}


def prove():
    graph_bytes = encode(graph())
    positives = []
    for take_exit in (True, False):
        raw = b''.join(encode(row) for row in track(take_exit))
        envelope = encode({'assignment_id': ASSIGNMENT, 'source_kind': 'synthetic_cpu',
                           'track_sha256': digest(raw), 'graph_sha256': digest(graph_bytes)})
        positives.append(measure(raw, graph_bytes, envelope))
    negatives = []
    base = track(False)
    for name, changed_rows, changed_graph in (
        ('no_connected_alternate', base, {**graph(), 'edges': [['hwy_before', 'hwy_after'], ['hwy_after', 'destination']]}),
        ('missing_follower', [{**r, 'behind': r['behind'][:1]} if r['frame'] == 240 else r for r in base], graph()),
        ('short_exit_window', base[:400], graph()),
        ('route_hop_without_exit', [{**r, 'ego': {**r['ego'], 'road': 'alternate'}} if r['frame'] == 300 else r for r in base], graph()),
    ):
        raw = b''.join(encode(row) for row in changed_rows)
        graw = encode(changed_graph)
        envelope = encode({'assignment_id': ASSIGNMENT, 'source_kind': 'synthetic_cpu',
                           'track_sha256': digest(raw), 'graph_sha256': digest(graw)})
        try:
            measure(raw, graw, envelope)
        except ValueError as error:
            negatives.append({'mutation': name, 'rejected_for': str(error)})
        else:
            raise AssertionError('negative accepted: ' + name)
    raw = b''.join(encode(row) for row in base)
    envelope = encode({'assignment_id': ASSIGNMENT, 'source_kind': 'synthetic_cpu',
                       'track_sha256': '0' * 64, 'graph_sha256': digest(graph_bytes)})
    try:
        measure(raw, graph_bytes, envelope)
    except ValueError as error:
        negatives.append({'mutation': 'changed_track_without_source_hash', 'rejected_for': str(error)})
    else:
        raise AssertionError('unbound trace accepted')
    receipt = {'format': 'c230259-route-cpu-proof-v1', 'script_sha256': digest(Path(__file__).read_bytes()),
               'positives': positives, 'negatives': negatives,
               'original_native_observed': False, 'delivery_ready': False}
    (HERE / 'route-cpu-proof.json').write_bytes(json.dumps(receipt, indent=2).encode() + b'\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prove', action='store_true')
    args = parser.parse_args()
    if args.prove:
        proof = prove()
        print(json.dumps({'positives': len(proof['positives']), 'negatives': len(proof['negatives'])}))
