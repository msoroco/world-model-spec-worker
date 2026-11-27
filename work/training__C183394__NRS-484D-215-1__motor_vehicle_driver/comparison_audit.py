"""Independent source-bound audit of the paired original beam attempts.

The comparison reports measured differences. It never assigns a legal verdict.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'native'))
from compare_beam import compare


CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')
FIXED_CONFIG = ('cell_id', 'law_id', 'actor', 'rate_hz', 'duration_s',
                'cameras', 'acceleration_gain', 'requested_speed_mps',
                'required_atoms', 'source_packets')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_delivery(attempt, audit_path, case):
    attempt = Path(attempt).resolve()
    audit_path = Path(audit_path).resolve()
    audit = json.loads(audit_path.read_text())
    if audit.get('format') != 'worker-delivery-audit' or audit.get('passed') is not True \
            or audit.get('case_id') != case or audit.get('checks') != dict.fromkeys(CHECKS, True):
        raise ValueError('Exact original delivery audit missing: ' + case)
    result = attempt / 'result.json'
    if not result.is_file() or audit.get('source_result_sha256') != sha(result):
        raise ValueError('Original result hash differs: ' + case)
    if Path(audit.get('video', '')).is_absolute() or Path(audit.get('trace', '')).is_absolute():
        raise ValueError('Original audit source must be attempt-relative: ' + case)
    for key, hash_key in (('video', 'video_sha256'), ('trace', 'trace_sha256')):
        source = (attempt / audit[key]).resolve()
        if attempt not in source.parents or not source.is_file() or sha(source) != audit.get(hash_key):
            raise ValueError('Original audit source hash differs: ' + key)
    if audit.get('frames') != 600 or audit.get('legal_verdict_claimed') is not False:
        raise ValueError('Original delivery audit frame or verdict differs: ' + case)
    return audit


def check_fixed_configuration(a, b):
    first = json.loads((Path(a) / 'config.json').read_text())
    second = json.loads((Path(b) / 'config.json').read_text())
    if any(first.get(key) != second.get(key) for key in FIXED_CONFIG):
        raise ValueError('Fixed beam comparison configuration differs')
    if first.get('beam_mode') != 'dim_within_500' or second.get('beam_mode') != 'retain_high':
        raise ValueError('Selected beam comparison policy differs')
    if any(first.get(key) is None for key in FIXED_CONFIG):
        raise ValueError('Fixed beam comparison configuration missing')
    return {key: first[key] for key in FIXED_CONFIG}


def audit_pair(attempt_a, attempt_b, delivery_a, delivery_b, output):
    a, b = Path(attempt_a).resolve(), Path(attempt_b).resolve()
    observation = compare(a, b)
    case_a, case_b = observation['case_ids']
    first = require_delivery(a, delivery_a, case_a)
    second = require_delivery(b, delivery_b, case_b)
    fixed = check_fixed_configuration(a, b)
    if first['recording_id'] == second['recording_id']:
        raise ValueError('Beam comparison requires distinct original recordings')
    payload = {'format': 'worker-comparison-audit', 'passed': True,
               'case_ids': [case_a, case_b],
               'comparison_id': observation['comparison_id'],
               'delivery_audit_sha256': [sha(delivery_a), sha(delivery_b)],
               'recording_ids': [first['recording_id'], second['recording_id']],
               'fixed_source_count': observation['fixed_source_count'],
               'fixed_configuration': fixed,
               'joined_frames': observation['joined_frames'],
               'trajectory_tolerance_m': observation['trajectory_tolerance_m'],
               'contrasting_within_500_feet_frames': observation['contrasting_within_500_feet_frames'],
               'physical_glare_conclusion': None, 'legal_verdict_claimed': False}
    target = Path(output).resolve()
    if target.exists():
        raise ValueError('Retain prior beam comparison audit')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, allow_nan=False) + '\n')
    return payload


def self_test(negative):
    import tempfile
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        attempt = root / 'attempt'; attempt.mkdir()
        (attempt / 'result.json').write_text('{}\n')
        (attempt / 'video.mkv').write_text('diagnostic bytes\n')
        (attempt / 'trace.json').write_text('{}\n')
        case = 'training__C183394__NRS-484D-215-1__motor_vehicle_driver__selected_6fb122bc__condition_a'
        receipt = {'format': 'worker-delivery-audit', 'passed': True,
                   'case_id': case, 'checks': dict.fromkeys(CHECKS, True),
                   'source_result_sha256': sha(attempt / 'result.json'),
                   'video': 'video.mkv', 'video_sha256': sha(attempt / 'video.mkv'),
                   'trace': 'trace.json', 'trace_sha256': sha(attempt / 'trace.json'),
                   'frames': 600, 'recording_id': 'cpu-only', 'legal_verdict_claimed': False}
        path = root / 'delivery.json'; path.write_text(json.dumps(receipt) + '\n')
        if negative:
            (attempt / 'video.mkv').write_text('changed diagnostic bytes\n')
            require_delivery(attempt, path, case)
            raise AssertionError('Changed source accepted')
        require_delivery(attempt, path, case)
        receipt['checks']['actual_pixels'] = False
        path.write_text(json.dumps(receipt) + '\n')
        try:
            require_delivery(attempt, path, case)
        except ValueError as error:
            assert 'delivery audit missing' in str(error)
        else:
            raise AssertionError('Missing pixel audit accepted')
        common = dict(cell_id='C183394', law_id='NRS-484D-215-1',
                      actor='motor_vehicle_driver', rate_hz=20, duration_s=30,
                      cameras=['overview', 'approach', 'reference_corner', 'driver_reference'],
                      acceleration_gain=.2, requested_speed_mps=2.5,
                      required_atoms=[], source_packets=[])
        other = root / 'other'; other.mkdir()
        (attempt / 'config.json').write_text(json.dumps(dict(common, beam_mode='dim_within_500')) + '\n')
        (other / 'config.json').write_text(json.dumps(dict(common, beam_mode='retain_high')) + '\n')
        assert check_fixed_configuration(attempt, other)['duration_s'] == 30
        changed = dict(common, beam_mode='retain_high', duration_s=29)
        (other / 'config.json').write_text(json.dumps(changed) + '\n')
        try:
            check_fixed_configuration(attempt, other)
        except ValueError as error:
            assert 'fixed' in str(error).lower()
        else:
            raise AssertionError('Changed duration accepted')
    return {'source_binding_checked': True, 'original_capture_attested': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--attempt-a'); parser.add_argument('--attempt-b')
    parser.add_argument('--delivery-a'); parser.add_argument('--delivery-b')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.self_test:
        value = self_test(args.negative)
    else:
        if not all((args.attempt_a, args.attempt_b, args.delivery_a, args.delivery_b, args.output)):
            parser.error('Both attempts, delivery audits and output are required')
        value = audit_pair(args.attempt_a, args.attempt_b, args.delivery_a,
                           args.delivery_b, args.output)
    print(json.dumps(value, indent=2))
