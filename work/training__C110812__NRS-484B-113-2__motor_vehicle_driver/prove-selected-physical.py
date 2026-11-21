"""CPU-only diagnostic of the selected reverse maneuver and ownership order.

The samples are synthetic Native-shaped fixtures, never original CARLA evidence.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(suffix, kind):
    if suffix not in ('false', 'true'):
        raise ValueError('Unknown selected case')
    entry = next(e for e in json.loads((HERE / 'control-proof-manifest.json').read_text())['cases']
                 if e['case_id'].endswith('__' + suffix))
    case_id = entry['case_id']
    base = {'case_id': case_id, 'construction_sha256': entry['construction_sha256'],
            'cpu_fixture_mock': True, 'original_native_motion_verified': False,
            'accepted': False, 'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        return {**base, 'events': EVENTS, 'exit_code': 0}
    if kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown physical fixture kind')
    spec_path = HERE / ('selected-diagnostic-condition_' + ('a' if suffix == 'false' else 'b') + '.json')
    recipe_path = HERE / ('selected-diagnostic-condition_' + ('a' if suffix == 'false' else 'b') + '-recipe.json')
    recipe = json.loads(recipe_path.read_text())
    if recipe['generator']['sha256'] != sha(spec_path):
        raise ValueError('Selected fixture recipe changed')
    spec = json.loads(spec_path.read_text())
    raw = spec['files'].get('native_samples.jsonl')
    if raw is None:
        raise ValueError('Missing selected Native-shaped diagnostic source')
    rows = [json.loads(line) for line in raw.splitlines()]
    if len(rows) != 840 or [r['native_frame'] for r in rows] != list(range(100, 940)):
        raise ValueError('Selected fixture frame continuity differs')
    if kind == 'missing_evidence':
        rows = []
    elif kind == 'incomplete_motion':
        rows = rows[:100]
    backing = [r for r in rows if r['signed_forward_velocity_m_s'] < -0.05]
    heading = max((abs((r['heading_deg'] - rows[0]['heading_deg'] + 180) % 360 - 180)
                   for r in backing), default=0)
    final_stop = bool(rows and abs(rows[-1]['signed_forward_velocity_m_s']) <= 0.05)
    time_join = all(r['video_frame'] == i and abs(r['time_s'] - (r['native_frame'] - 99) / 20) < 1e-6
                    for i, r in enumerate(rows))
    full_body = all(len(r.get('native_body_xy_m', [])) == 4 and
                    r.get('native_corner_survey') is True for r in rows)
    completed = (len(rows) == 840 and len(backing) >= 20 and final_stop and time_join
                 and full_body and ((suffix == 'true' and heading >= 30)
                                    or (suffix == 'false' and heading < 12)))
    status = 'unverified' if not rows else 'met' if completed else 'not_met'
    return {**base, 'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'mock_input_provenance': 'synthetic_native_sample',
            'physical_checks': {'maneuver': {'status': status,
                'method': '840 joined Native-shaped pose/body/velocity samples, reverse heading and final stop',
                'sources': [str(spec_path.relative_to(HERE))] if rows else ['missing diagnostic Native samples']}},
            'maneuver_completed': completed,
            'realized_observables': ({'sample_count': len(rows), 'reverse_frames': len(backing),
                                      'max_reverse_heading_change_deg': heading,
                                      'final_stop': final_stop, 'joined': time_join,
                                      'full_body_and_survey': full_body} if rows else {}),
            'retained_source_sha256': {'native_samples.jsonl': hashlib.sha256(raw.encode()).hexdigest()} if rows else {}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--suffix', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.suffix, args.kind)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': result['case_id'], 'kind': args.kind,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status', 'lifecycle'),
                      'original_native_motion_verified': False}))


if __name__ == '__main__':
    main()
