"""Synthetic saved-geometry proof for the scooter passing boundary.

Every figure here is an authored CPU diagnostic. Native body geometry, actor
identity, road lane count, and safe-clear judgment still require real sources.
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
FEET_TO_M = 0.3048
MIN_GAP_M = 3 * FEET_TO_M
EGO_HALF_LENGTH = 2.2
EGO_HALF_WIDTH = 0.9
SCOOTER_HALF_LENGTH = 0.75
SCOOTER_HALF_WIDTH = 0.35
SCOOTER_Y = -1.75
TARGETS = {'witness_1': 1.2, 'witness_2': 0.8,
           'numeric_1_0': 2.9 * FEET_TO_M,
           'numeric_1_1': 3.0 * FEET_TO_M,
           'numeric_1_2': 3.1 * FEET_TO_M}


def encode(obj):
    return (json.dumps(obj, sort_keys=True, separators=(',', ':')) + '\n').encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(value, reason):
    if not value:
        raise ValueError(reason)


def trace(gap_m, early_return=False):
    rows = []
    pass_y = SCOOTER_Y + SCOOTER_HALF_WIDTH + EGO_HALF_WIDTH + gap_m
    for frame in range(FRAMES):
        t = frame / HZ
        ego_x = -30 + 4 * t
        scooter_x = -10 + 2 * t
        # The lane movement is a requested maneuver. During overlap, both
        # footprints have constant y; return is intentionally after passing.
        if t < 5:
            y = -1.75 + (pass_y + 1.75) * t / 5
        elif t < (10 if early_return else 17):
            y = pass_y
        elif t < (12 if early_return else 20):
            begin = 10 if early_return else 17
            y = pass_y + (-1.75 - pass_y) * (t - begin) / 3
        else:
            y = -1.75
        rows.append({'frame': frame, 'time_s': t, 'source_kind': 'synthetic_cpu',
                     'ego': {'id': 'ego', 'center_xy_m': [ego_x, y],
                             'half_length_m': EGO_HALF_LENGTH,
                             'half_width_m': EGO_HALF_WIDTH},
                     'scooter': {'id': 'electric_scooter',
                                 'center_xy_m': [scooter_x, SCOOTER_Y],
                                 'half_length_m': SCOOTER_HALF_LENGTH,
                                 'half_width_m': SCOOTER_HALF_WIDTH}})
    return rows


def surface_gap(a, b):
    ax, ay = a['center_xy_m']
    bx, by = b['center_xy_m']
    dx = max(0.0, abs(ax - bx) - a['half_length_m'] - b['half_length_m'])
    dy = max(0.0, abs(ay - by) - a['half_width_m'] - b['half_width_m'])
    return math.hypot(dx, dy)


def measure(raw, context_raw, envelope_raw):
    context = json.loads(context_raw)
    envelope = json.loads(envelope_raw)
    require(envelope.get('assignment_id') == ASSIGNMENT
            and envelope.get('trace_sha256') == digest(raw)
            and envelope.get('context_sha256') == digest(context_raw),
            'source identity or hash differs')
    require(context.get('source_kind') == 'synthetic_cpu'
            and context.get('same_direction_lanes') == 1
            and context.get('subject_type') == 'motor_vehicle_driver'
            and context.get('overtaken_type') == 'electric_scooter',
            'one-lane scooter activation context missing')
    rows = [json.loads(line) for line in raw.splitlines() if line]
    require(len(rows) == FRAMES, 'full 30-second trace missing')
    overlap = []
    right_return = None
    last_abreast = None
    for frame, row in enumerate(rows):
        require(row.get('frame') == frame and row.get('time_s') == frame / HZ
                and row.get('source_kind') == 'synthetic_cpu',
                'time/source join differs')
        ego, scooter = row['ego'], row['scooter']
        require(ego['id'] == 'ego' and scooter['id'] == 'electric_scooter',
                'actor identity differs')
        for actor in (ego, scooter):
            vals = actor['center_xy_m'] + [actor['half_length_m'], actor['half_width_m']]
            require(all(type(v) in (float, int) and math.isfinite(v) for v in vals)
                    and actor['half_length_m'] > 0 and actor['half_width_m'] > 0,
                    'body geometry missing')
        ego_x, ego_y = ego['center_xy_m']
        scooter_x, scooter_y = scooter['center_xy_m']
        x_overlap = abs(ego_x - scooter_x) <= ego['half_length_m'] + scooter['half_length_m']
        if x_overlap:
            require(ego_y > scooter_y, 'pass not to scooter left')
            gap = surface_gap(ego, scooter)
            overlap.append((frame, gap))
            last_abreast = frame
        if right_return is None and frame > 0 and ego_y < rows[frame-1]['ego']['center_xy_m'][1] - 1e-8:
            right_return = frame
    require(overlap and right_return is not None, 'pass or return phase absent')
    min_frame, min_gap = min(overlap, key=lambda item: item[1])
    require(right_return > last_abreast, 'return began before vehicle was longitudinally clear')
    return {'format': 'c272412-scooter-pass-cpu-facts-v1',
            'trace_sha256': digest(raw), 'context_sha256': digest(context_raw),
            'frame_count': FRAMES, 'rate_hz': HZ,
            'abreast_frames': len(overlap), 'minimum_surface_gap_m': min_gap,
            'minimum_gap_frame': min_frame, 'statutory_floor_m': MIN_GAP_M,
            'three_feet_met_in_synthetic_geometry': min_gap + 1e-10 >= MIN_GAP_M,
            'last_abreast_frame': last_abreast, 'right_return_start_frame': right_return,
            'safe_clear_legally_determined': False, 'original_native_observed': False,
            'legal_result': None}


def envelope(raw, context_raw):
    return encode({'assignment_id': ASSIGNMENT, 'trace_sha256': digest(raw),
                   'context_sha256': digest(context_raw)})


def prove():
    context = encode({'source_kind': 'synthetic_cpu', 'same_direction_lanes': 1,
                      'subject_type': 'motor_vehicle_driver',
                      'overtaken_type': 'electric_scooter',
                      'actual_lane_count_verified': False})
    positives = []
    for suffix, target in TARGETS.items():
        raw = b''.join(encode(row) for row in trace(target))
        facts = measure(raw, context, envelope(raw, context))
        require(abs(facts['minimum_surface_gap_m'] - target) < 1e-9,
                'requested geometry measurement differs')
        positives.append({'case_suffix': suffix, 'requested_gap_m': target, 'facts': facts})
    negatives = []
    base = trace(1.2)
    variants = [
        ('early_return', trace(1.2, early_return=True), context),
        ('missing_frame', base[:299] + base[300:], context),
        ('wrong_lane_count', base, encode({**json.loads(context), 'same_direction_lanes': 2})),
        ('wrong_actor', [{**r, 'scooter': {**r['scooter'], 'id': 'unknown'}} if r['frame'] == 240 else r for r in base], context),
    ]
    for name, rows, ctx in variants:
        raw = b''.join(encode(row) for row in rows)
        try:
            measure(raw, ctx, envelope(raw, ctx))
        except ValueError as error:
            negatives.append({'mutation': name, 'rejected_for': str(error)})
        else:
            raise AssertionError('altered source accepted: ' + name)
    raw = b''.join(encode(row) for row in base)
    bad_envelope = encode({'assignment_id': ASSIGNMENT, 'trace_sha256': '0' * 64,
                           'context_sha256': digest(context)})
    try:
        measure(raw, context, bad_envelope)
    except ValueError as error:
        negatives.append({'mutation': 'unbound_source', 'rejected_for': str(error)})
    else:
        raise AssertionError('unbound source accepted')
    proof = {'format': 'c272412-pass-cpu-proof-v1',
             'script_sha256': digest(Path(__file__).read_bytes()),
             'positives': positives, 'negatives': negatives,
             'native_observed': False, 'delivery_ready': False}
    (HERE / 'pass-cpu-proof.json').write_bytes(json.dumps(proof, indent=2).encode() + b'\n')
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prove', action='store_true')
    args = parser.parse_args()
    if args.prove:
        receipt = prove()
        print(json.dumps({'positives': len(receipt['positives']),
                          'negatives': len(receipt['negatives'])}))
