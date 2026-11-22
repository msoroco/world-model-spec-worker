"""CPU-only completion tri-state for the separate lawful control candidate."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def run(kind):
    entry = next(e for e in json.loads((HERE / 'current-runtime-reproof-manifest.json').read_text())['cases']
                 if e['case_id'].endswith('__control'))
    base = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
            'cpu_fixture_mock': True, 'original_native_motion_verified': False,
            'accepted': False, 'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        return {**base, 'events': EVENTS, 'exit_code': 0}
    if kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown fixture kind')
    spec = json.loads((HERE / 'selected-diagnostic-condition_c.json').read_text())
    raw = spec['files']['native_samples.jsonl']
    rows = [json.loads(line) for line in raw.splitlines()]
    if kind == 'missing_evidence':
        rows = []
    elif kind == 'incomplete_motion':
        rows = rows[:100]
    reverse = [r for r in rows if r['signed_forward_velocity_m_s'] < -0.05]
    clear = all(min(v[0] for v in r['native_body_xy_m']) > 7 and
                max(v[0] for v in r['native_body_xy_m']) < 100 for r in rows)
    joined = all(r['native_frame'] == 100 + i and r['video_frame'] == i and
                 abs(r['time_s'] - (i + 1) / 20) < 1e-6 for i, r in enumerate(rows))
    stopped = bool(rows and abs(rows[-1]['signed_forward_velocity_m_s']) <= 0.05)
    complete = len(rows) == 840 and len(reverse) >= 20 and clear and joined and stopped
    status = 'unverified' if not rows else 'met' if complete else 'not_met'
    return {**base, 'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'mock_input_provenance': 'synthetic_native_sample',
            'physical_checks': {'maneuver': {'status': status,
                'method': '840 joined Native-shaped reverse/body samples, no prohibited-region entry and final stop',
                'sources': ['selected-diagnostic-condition_c.json'] if rows else ['missing diagnostic Native samples']}},
            'maneuver_completed': complete,
            'realized_observables': ({'sample_count': len(rows), 'reverse_frames': len(reverse),
                                      'body_clear_of_intersection': clear, 'joined': joined,
                                      'final_stop': stopped} if rows else {}),
            'retained_source_sha256': {'native_samples.jsonl': hashlib.sha256(raw.encode()).hexdigest()} if rows else {}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.kind)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'kind': args.kind,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status', 'lifecycle'),
                      'original_native_motion_verified': False}))
