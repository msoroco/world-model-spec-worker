"""Independent source-bound CPU comparisons for C223016 diagnostic cases.

The paired values are synthetic construction premises. This audit does not infer
municipal authorization, actual camera legibility, or Native physical success.
"""
import argparse
import hashlib
import json
import math
import shlex
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(case_id, manifest):
    entry = next(x for x in manifest['cases'] if x['case_id'] == case_id)
    binding = entry['saved_processing_proof']
    receipt_path = HERE / binding['log']
    if digest(receipt_path) != binding['log_sha256']:
        raise ValueError('Saved receipt binding differs')
    receipt = json.loads(receipt_path.read_text())
    if (receipt['case_id'] != case_id or receipt['candidate_id'] != 'primary'
            or not receipt['passed'] or receipt['missing_evidence']
            or not receipt['recorded_only'] or not receipt['originals_preserved']
            or receipt['physical_acceptance_claimed'] or receipt['legal_acceptance_claimed']
            or receipt['native_revision']['construction_sha256'] != entry['construction_sha256']):
        raise ValueError('Primary source-only saved processing incomplete')
    command = shlex.split(binding['command'])
    root = Path(command[command.index('--attempt') + 1])
    source = root / 'direction_state.jsonl'
    if digest(source) != receipt['original_source_hashes']['direction_state.jsonl']:
        raise ValueError('Original direction source hash differs')
    result_path = Path(receipt['result'])
    if digest(result_path) != receipt['result_sha256']:
        raise ValueError('Measured result hash differs')
    result = json.loads(result_path.read_text())
    measurement = result.get('measured_values', {}).get('reversible_direction')
    if not measurement or not all(x.get('matched') for x in result['target_checks']):
        raise ValueError('Saved comparison member has no matching measurement')
    rows = [json.loads(x) for x in source.read_text().splitlines()]
    if not rows or len(rows) != measurement['frames']:
        raise ValueError('Original direction frame count differs')
    return {'entry': entry, 'receipt': receipt, 'measurement': measurement,
            'rows': rows, 'config': json.loads((root / 'config.json').read_text())}


def _pose(row):
    pose = row['device'].get('native_pose')
    if not isinstance(pose, dict):
        raise ValueError('Original device pose missing')
    for key in ('position_m', 'rotation_deg'):
        values = pose.get(key)
        if not isinstance(values, list) or len(values) != 3 or any(
                not isinstance(value, (int, float)) or not math.isfinite(value)
                for value in values):
            raise ValueError('Original device pose invalid')
    return pose


def _marking_anchor(row):
    anchor = row['device'].get('marking_anchor')
    if not isinstance(anchor, dict) or not isinstance(anchor.get('marking'), dict):
        raise ValueError('Original marking anchor missing')
    if (anchor['marking'].get('source_id') != row['device'].get('source_id')
            or anchor.get('road_id') != anchor['marking'].get('road_id')
            or anchor.get('lane_id') != row.get('lane_id')):
        raise ValueError('Original marking anchor identity differs')
    for key in ('s_m', 'lane_width_m'):
        value = anchor.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('Original marking anchor invalid')
    for key in ('position_m', 'rotation_deg'):
        values = anchor.get(key)
        if not isinstance(values, list) or len(values) != 3 or any(
                not isinstance(value, (int, float)) or not math.isfinite(value)
                for value in values):
            raise ValueError('Original marking anchor invalid')
    return anchor


def compare(comparison_id, *, tamper=False, tamper_pose=False):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    spec = next(x for x in plan['comparisons'] if x['comparison_id'] == comparison_id)
    if len(spec['case_ids']) != 2:
        raise ValueError('Comparison requires exactly two exact cases')
    left, right = [load(x, manifest) for x in spec['case_ids']]
    if tamper:
        right['rows'][0]['device']['source_id'] = 'tampered-device'
    pose_comparisons = {'morning_direction', 'evening_direction',
                        'period_reversal', 'sign_direction',
                        'centerline_override', 'signal_direction'}
    if tamper_pose:
        if comparison_id == 'marking_direction':
            right['rows'][0]['device']['marking_anchor']['position_m'][0] += 1.0
        elif comparison_id in pose_comparisons:
            right['rows'][0]['device']['native_pose']['position_m'][0] += 1.0
        else:
            raise ValueError('Geometry tamper requires a device comparison')
    a, b = left['config'], right['config']
    fixed = ('governed_lane_id', 'rate_hz', 'frames', 'duration_s', 'cameras')
    if any(a.get(k) != b.get(k) for k in fixed):
        raise ValueError('Controlled comparison changed fixed capture or lane')
    reversal = comparison_id == 'period_reversal'
    if reversal:
        if (a['subject_direction_xy'] != b['subject_direction_xy']
                or a['period_id'] == b['period_id']
                or a['period_direction_xy'] == b['period_direction_xy']):
            raise ValueError('Period reversal failed to isolate period and designation')
    elif (a['period_id'] != b['period_id']
          or a['period_direction_xy'] != b['period_direction_xy']
          or a['subject_direction_xy'] == b['subject_direction_xy']):
        raise ValueError('Direction comparison failed to isolate subject heading')
    lhs, rhs = left['rows'], right['rows']
    if len(lhs) != len(rhs):
        raise ValueError('Comparison frame counts differ')
    if comparison_id in pose_comparisons:
        fixed_pose = _pose(lhs[0])
        if any(_pose(row) != fixed_pose for row in lhs + rhs):
            raise ValueError('Controlled comparison changed original device pose')
    if comparison_id == 'marking_direction':
        fixed_anchor = _marking_anchor(lhs[0])
        if any(_marking_anchor(row) != fixed_anchor for row in lhs + rhs):
            raise ValueError('Controlled comparison changed original marking anchor')
    for x, y in zip(lhs, rhs):
        if (x['frame'], x['time_s'], x['lane_id']) != (y['frame'], y['time_s'], y['lane_id']):
            raise ValueError('Controlled comparison changed frame/time/lane')
        if (x['device']['source_id'], x['device']['kind'], x['device']['governs_lane_id']) != (
                y['device']['source_id'], y['device']['kind'], y['device']['governs_lane_id']):
            raise ValueError('Controlled comparison changed device identity or lane')
        if reversal:
            if (x['subject_velocity_xy'] != y['subject_velocity_xy']
                    or x['device']['direction_xy'] == y['device']['direction_xy']
                    or x['civil_time']['iso8601'] == y['civil_time']['iso8601']):
                raise ValueError('Period reversal source variation differs')
        elif (x['device'] != y['device'] or x['civil_time'] != y['civil_time']
              or x['subject_velocity_xy'] == y['subject_velocity_xy']):
            raise ValueError('Direction comparison source variation differs')
    if comparison_id == 'centerline_override':
        first = left['measurement'].get('direction')
        second = right['measurement'].get('direction')
        if (first, second) != ('with_designation', 'against_designation'):
            raise ValueError('Centerline direction results differ')
        for member in (left, right):
            receipt_result = json.loads(Path(member['receipt']['result']).read_text())
            centerline = receipt_result['measured_values'].get('centerline_override')
            if (not centerline or centerline['marking_type'] != 'Solid'
                    or centerline['minimum_heading_opposition'] < .95):
                raise ValueError('Contrary centerline measurement absent')
    outcomes = [x['measurement']['direction'] for x in (left, right)]
    if outcomes != ['with_designation', 'against_designation']:
        raise ValueError('Controlled outcomes do not distinguish the pair')
    return {'comparison_id': comparison_id, 'case_ids': spec['case_ids'],
            'saved_result_sha256': [x['receipt']['result_sha256'] for x in (left, right)],
            'original_direction_source_sha256': [x['receipt']['original_source_hashes']['direction_state.jsonl'] for x in (left, right)],
            'joined_frames': len(lhs), 'measured_outcomes': outcomes,
            'fixed_source_conditions_verified': True,
            'source_device_geometry_contract_verified': (
                comparison_id in pose_comparisons or comparison_id == 'marking_direction'),
            'synthetic_diagnostic_only': True, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--tamper', action='store_true')
    parser.add_argument('--tamper-pose', action='store_true')
    args = parser.parse_args()
    print(json.dumps(compare(args.comparison, tamper=args.tamper,
                             tamper_pose=args.tamper_pose)))
