"""Audit the finite C223016 commanded-speed grid from retained saved originals.

All current inputs are synthetic CPU diagnostics. No legal speed threshold is inferred.
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    rows = [json.loads(s) for s in Path(path).read_text().splitlines() if s]
    if not rows:
        raise ValueError('Empty original source')
    return rows


def member(speed, attempt, receipt_path):
    attempt, receipt_path = Path(attempt), Path(receipt_path)
    receipt = json.loads(receipt_path.read_text())
    suffix = 'morning_east_with' if speed == 5 else f'morning_east_speed_{speed}'
    case_id = HERE.name + '__' + suffix
    if (receipt['case_id'] != case_id or receipt['candidate_id'] != 'primary'
            or not receipt['passed'] or receipt['missing_evidence']
            or not receipt['recorded_only'] or not receipt['originals_preserved']
            or receipt['physical_acceptance_claimed'] or receipt['legal_acceptance_claimed']):
        raise ValueError('Saved source-only receipt incomplete')
    construction = HERE / ('construction.json' if speed == 5 else f'numeric-speed-{speed}-construction.json')
    if receipt['native_revision']['construction_sha256'] != sha(construction):
        raise ValueError('Saved construction hash differs')
    for name in ('direction_state.jsonl', 'trace.jsonl', 'capture/evidence.jsonl',
                 'config.json', 'video_frames.jsonl'):
        if sha(attempt / name) != receipt['original_source_hashes'][name]:
            raise ValueError('Original source hash differs: ' + name)
    result_path = Path(receipt['result'])
    if sha(result_path) != receipt['result_sha256']:
        raise ValueError('Saved measurement hash differs')
    result = json.loads(result_path.read_text())
    measure = result['measured_values']['reversible_direction']
    if (measure['direction'] != 'with_designation' or measure['legal_judgment'] is not None
            or not all(x['matched'] for x in result['target_checks'])):
        raise ValueError('Source direction outcome differs')
    config = json.loads((attempt / 'config.json').read_text())
    if config['target_speed_mps'] != speed:
        raise ValueError('Commanded numeric grid differs')
    rows = read_rows(attempt / 'direction_state.jsonl')
    trace = read_rows(attempt / 'trace.jsonl')
    evidence = read_rows(attempt / 'capture/evidence.jsonl')
    if len(rows) != len(trace) or len(rows) != len(evidence) or len(rows) != measure['frames']:
        raise ValueError('Original source frame counts differ')
    velocities = []
    for r, t, e in zip(rows, trace, evidence):
        if (r['frame'] != t['frame'] or r['frame'] != e['original_frame']
                or abs(r['time_s'] - t['time_s']) > 1e-6
                or abs(r['subject_velocity_xy'][0] - t['speed_mps']) > 1e-6
                or abs(r['subject_velocity_xy'][0] - e['ego']['speed_mps']) > 1e-6
                or abs(r['subject_velocity_xy'][1]) > 1e-6):
            raise ValueError('Source velocity, frame, or time join differs')
        velocities.append(r['subject_velocity_xy'][0])
    if max(velocities) - min(velocities) > 1e-6:
        raise ValueError('Diagnostic source speed changed inside capture')
    if not (attempt / 'fixture-provenance.json').is_file():
        raise ValueError('Current proof must label synthetic diagnostic provenance')
    device = rows[0]['device']
    if any(r['device'] != device or r['lane_id'] != rows[0]['lane_id'] for r in rows):
        raise ValueError('Original governed source changed inside capture')
    return {'case_id': case_id, 'commanded_speed_mps': speed,
            'source_speed_mps': velocities[0], 'frames': len(rows),
            'direction_source_sha256': receipt['original_source_hashes']['direction_state.jsonl'],
            'trace_sha256': receipt['original_source_hashes']['trace.jsonl'],
            'config': config, 'device': device, 'lane_id': rows[0]['lane_id'],
            'period': rows[0]['civil_time']['iso8601'], 'receipt_sha256': sha(receipt_path)}


def audit(pairs):
    points = [member(speed, *pairs[speed]) for speed in (3, 5, 7)]
    baseline = points[1]
    for point in points:
        a, b = point['config'], baseline['config']
        for key in ('period_id', 'period_direction_xy', 'subject_direction_xy',
                    'governed_lane_id', 'rate_hz', 'frames', 'duration_s', 'cameras'):
            if a[key] != b[key]:
                raise ValueError('Numeric sweep changed fixed condition: ' + key)
        if (point['device'] != baseline['device'] or point['lane_id'] != baseline['lane_id']
                or point['period'] != baseline['period']):
            raise ValueError('Numeric sweep changed original device or civil period')
    if [p['source_speed_mps'] for p in points] != [2.0, 4.0, 6.0]:
        raise ValueError('Finite source-backed speed grid differs')
    return {'axis': 'original same-frame subject speed_mps', 'points': [
        {k: p[k] for k in ('case_id', 'commanded_speed_mps', 'source_speed_mps',
                          'frames', 'direction_source_sha256', 'trace_sha256', 'receipt_sha256')}
        for p in points], 'fixed_device_and_period_verified': True,
        'synthetic_diagnostic_only': True, 'legal_threshold_inferred': False,
        'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for speed in (3, 5, 7):
        parser.add_argument(f'--attempt-{speed}', required=True)
        parser.add_argument(f'--receipt-{speed}', required=True)
    args = parser.parse_args()
    pairs = {s: (getattr(args, f'attempt_{s}'), getattr(args, f'receipt_{s}')) for s in (3, 5, 7)}
    print(json.dumps(audit(pairs)))
