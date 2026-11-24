"""Compare the selected curbside manner pair after independent Native acceptance."""
import argparse
import hashlib
import json
from pathlib import Path


AID = 'training__C230222__LVMC-11-22-020__motor_vehicle_driver'
COMPARISON = AID + '__comparison'
CASES = (AID + '__probe_a', AID + '__probe_b')
FIXED = ('cell_id', 'law_id', 'actor', 'required_atoms', 'rate_hz',
         'duration_s', 'cameras', 'pedestrian_placement', 'vehicle_blueprint')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(comparison_id, left_path, right_path, output):
    require(comparison_id == COMPARISON, 'Select exact curbside comparison')
    records = [read(left_path), read(right_path)]
    require([record.get('case_id') for record in records] == list(CASES) and
            all(record.get('format') == 'worker-delivery-audit' and
                record.get('passed') is True and
                all(record.get('checks', {}).get(name) is True for name in
                    ('native_source', 'all_participants', 'time_join',
                     'full_video_decode', 'actual_pixels', 'physical_completion'))
                for record in records),
            'Comparison requires independent original delivery acceptance')
    attempts = [Path(record['attempt_path']).resolve() for record in records]
    configs = [read(path / 'config.json') for path in attempts]
    for name in FIXED:
        require(configs[0].get(name) == configs[1].get(name),
                'Controlled curbside condition differs: ' + name)
    require([config.get('control_style') for config in configs] == [0, 1],
            'Selected controller sweep points differ')
    results = []
    for case, record, attempt in zip(CASES, records, attempts):
        require(record.get('capture_seal_sha256') == sha(attempt / 'capture-seal.json') and
                record.get('trace_sha256') == sha(attempt / 'trace.jsonl') and
                record.get('video_sha256') == sha(attempt / 'overview.mkv'),
                'Accepted original source changed before comparison')
        saved = Path(record['saved_path'])
        processing = read(saved / 'processing.json')
        result = read(Path(processing['result']))
        require(result.get('case_id') == case and result.get('legal_acceptance_claimed') is False,
                'Comparison source has an unsupported legal judgment')
        results.append({'case_id': case,
                        'source_result_sha256': sha(Path(processing['result'])),
                        'measured_values': result.get('measured_values', {}),
                        'physical_checks': result.get('physical_checks', {}),
                        'realized_observables': result.get('realized_observables', {})})
    report = {'format': 'worker-comparison-audit', 'comparison_id': comparison_id,
              'case_ids': list(CASES), 'passed': True,
              'fixed_conditions': list(FIXED),
              'deliberate_differences': ['control_style'],
              'source_delivery_audits': [sha(left_path), sha(right_path)],
              'results': results, 'legal_verdict_claimed': False}
    Path(output).write_text(json.dumps(report, indent=2) + '\n')
    return report


def selftest(comparison_id):
    require(comparison_id == COMPARISON, 'Select exact curbside comparison')
    assert len(CASES) == 2 and 'cameras' in FIXED
    try:
        require(False, 'test rejection')
    except ValueError as error:
        assert str(error) == 'test rejection'
    print('PASS exact curbside comparison identity, fixed fields and rejection helper')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left')
    parser.add_argument('--right')
    parser.add_argument('--output')
    parser.add_argument('--selftest', action='store_true')
    args = parser.parse_args()
    if args.selftest:
        selftest(args.comparison)
    else:
        compare(args.comparison, args.left, args.right, args.output)
