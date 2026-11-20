"""Compare two independently saved C223016 attempts from their retained originals.

A passing CPU comparison establishes source and measurement consistency only.
It does not establish Native physical success or municipal authority.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from comparison_audit import _marking_anchor, _pose

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def comparable_device(device):
    """Discard capture-local actor IDs while retaining the observed device state."""
    value = json.loads(json.dumps(device))
    value.pop('source_id', None)
    anchor = value.get('marking_anchor')
    if isinstance(anchor, dict) and isinstance(anchor.get('marking'), dict):
        anchor['marking'].pop('source_id', None)
    return value


def comparable_anchor(row):
    value = json.loads(json.dumps(_marking_anchor(row)))
    value['marking'].pop('source_id', None)
    return value


def member(case_id, attempt, receipt_path, manifest):
    attempt, receipt_path = Path(attempt), Path(receipt_path)
    entry = next(e for e in manifest['cases'] if e['case_id'] == case_id)
    receipt = json.loads(receipt_path.read_text())
    if (receipt['case_id'] != case_id or receipt['candidate_id'] != 'primary'
            or not receipt['passed'] or receipt['missing_evidence']
            or not receipt['recorded_only'] or not receipt['originals_preserved']
            or receipt['native_revision']['construction_sha256'] != entry['construction_sha256']):
        raise ValueError('Saved attempt is not a current source-only primary proof')
    if receipt['physical_acceptance_claimed'] or receipt['legal_acceptance_claimed']:
        raise ValueError('Saved receipt makes an unsupported acceptance claim')
    for name in ('direction_state.jsonl', 'config.json', 'video_frames.jsonl',
                 'body_history.jsonl'):
        if sha(attempt / name) != receipt['original_source_hashes'][name]:
            raise ValueError(f'Original source hash differs: {name}')
    result_path = Path(receipt['result'])
    if sha(result_path) != receipt['result_sha256']:
        raise ValueError('Measured result hash differs')
    result = json.loads(result_path.read_text())
    measurement = result['measured_values'].get('reversible_direction')
    if not measurement or not all(x.get('matched') for x in result['target_checks']):
        raise ValueError('Source-derived measured result absent')
    rows = [json.loads(line) for line in (attempt / 'direction_state.jsonl').read_text().splitlines()]
    if len(rows) != measurement['frames'] or not rows:
        raise ValueError('Original direction frame count differs')
    if (measurement['device_source_id'] != rows[0]['device']['source_id'] or
            measurement['lane_id'] != rows[0]['lane_id'] or
            measurement['period_id'] != rows[0]['device']['period_id']):
        raise ValueError('Measured result differs from original source identity')
    if any(rows[i]['frame'] >= rows[i + 1]['frame'] or
           rows[i]['time_s'] >= rows[i + 1]['time_s'] for i in range(len(rows) - 1)):
        raise ValueError('Original frame or time order invalid')
    provenance = attempt / 'fixture-provenance.json'
    return {'attempt': attempt, 'receipt': receipt, 'config': json.loads((attempt / 'config.json').read_text()),
            'measurement': measurement, 'rows': rows, 'diagnostic': provenance.exists()}


def audit(comparison_id, left_attempt, left_receipt, right_attempt, right_receipt):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    spec = next(x for x in plan['comparisons'] if x['comparison_id'] == comparison_id)
    if len(spec['case_ids']) != 2:
        raise ValueError('Comparison must bind two exact cases')
    lhs, rhs = [member(case_id, attempt, receipt, manifest) for case_id, attempt, receipt in
                zip(spec['case_ids'], (left_attempt, right_attempt), (left_receipt, right_receipt))]
    a, b = lhs['config'], rhs['config']
    for key in ('governed_lane_id', 'rate_hz', 'frames', 'duration_s', 'cameras'):
        if a.get(key) != b.get(key):
            raise ValueError(f'Fixed controlled condition changed: {key}')
    reversal = comparison_id == 'period_reversal'
    if reversal:
        if (a['subject_direction_xy'] != b['subject_direction_xy'] or
                a['period_id'] == b['period_id'] or
                a['period_direction_xy'] == b['period_direction_xy']):
            raise ValueError('Period reversal did not isolate period and designation')
    elif (a['period_id'] != b['period_id'] or
          a['period_direction_xy'] != b['period_direction_xy'] or
          a['subject_direction_xy'] == b['subject_direction_xy']):
        raise ValueError('Heading comparison did not isolate subject direction')
    lrows, rrows = lhs['rows'], rhs['rows']
    if len(lrows) != len(rrows):
        raise ValueError('Independent captures have different frame counts')
    kind = lrows[0]['device']['kind']
    if kind != rrows[0]['device']['kind']:
        raise ValueError('Original device kinds differ')
    geometry = (comparable_anchor(lrows[0]) if comparison_id == 'marking_direction'
                else _pose(lrows[0]))
    for row in lrows + rrows:
        other = (comparable_anchor(row) if comparison_id == 'marking_direction'
                 else _pose(row))
        if other != geometry:
            raise ValueError('Independent captures changed original device geometry')
        if (row['device']['kind'] != kind or
                row['device']['governs_lane_id'] != a['governed_lane_id'] or
                row['lane_id'] != a['governed_lane_id']):
            raise ValueError('Independent captures changed device kind or lane')
        if any(not math.isfinite(v) for v in row['subject_velocity_xy']):
            raise ValueError('Nonfinite original velocity')
    for rows in (lrows, rrows):
        if any(row['device']['source_id'] != rows[0]['device']['source_id'] for row in rows):
            raise ValueError('Original device source identity changed within an attempt')
    if reversal:
        if any(x['subject_velocity_xy'] != y['subject_velocity_xy'] or
               x['device']['direction_xy'] == y['device']['direction_xy'] or
               x['civil_time']['iso8601'] == y['civil_time']['iso8601']
               for x, y in zip(lrows, rrows)):
            raise ValueError('Period source variation differs')
    elif any(comparable_device(x['device']) != comparable_device(y['device']) or
             x['civil_time'] != y['civil_time'] or
             x['subject_velocity_xy'] == y['subject_velocity_xy']
             for x, y in zip(lrows, rrows)):
        raise ValueError('Heading source variation differs')
    outcomes = [lhs['measurement']['direction'], rhs['measurement']['direction']]
    if outcomes != ['with_designation', 'against_designation']:
        raise ValueError('Source-derived measured outcomes do not distinguish the pair')
    return {'comparison_id': comparison_id, 'case_ids': spec['case_ids'],
            'attempts': [str(lhs['attempt']), str(rhs['attempt'])],
            'source_sha256': [x['receipt']['original_source_hashes']['direction_state.jsonl']
                              for x in (lhs, rhs)],
            'capture_local_device_ids': [lrows[0]['device']['source_id'],
                                         rrows[0]['device']['source_id']],
            'measured_outcomes': outcomes, 'joined_frames': len(lrows),
            'independent_attempt_inputs': True,
            'diagnostic_inputs': lhs['diagnostic'] or rhs['diagnostic'],
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left-attempt', required=True)
    parser.add_argument('--left-receipt', required=True)
    parser.add_argument('--right-attempt', required=True)
    parser.add_argument('--right-receipt', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, args.left_attempt, args.left_receipt,
                           args.right_attempt, args.right_receipt)))
