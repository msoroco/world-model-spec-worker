"""Independent timing comparison; source facts only, without legal judgment."""
import argparse
import json
from pathlib import Path

from measure_timing import measure

HERE = Path(__file__).resolve().parent


def compare(early, late, early_config, late_config, action):
    for item in (early, late):
        if item.get('format') != 'c179480-source-timing-measurement-v1' or \
                item.get('frames') != 600 or item.get('rate_hz') != 20:
            raise ValueError('Missing exact same-tick timing measurement')
        if not all(item.get('source_sha256', {}).get(name) for name in
                   ('actor-sources.jsonl', 'camera-frames.jsonl')):
            raise ValueError('Original actor/camera source hashes incomplete')
        if not item.get('rear_same_lane_all_frames') or item.get('min_rear_surface_gap_m', 0) <= 0:
            raise ValueError('Immediately rear source relation missing')
        if item.get('diagnostic_threshold_is_law') is not False or \
                item.get('legal_appropriateness') is not None:
            raise ValueError('Unsupported legal timing or signal claim')
    if early['fixed_motion_sha256'] != late['fixed_motion_sha256']:
        raise ValueError('Fixed actor motion or rear relation differs')
    fixed_keys = ('cell_id', 'law_id', 'actor', 'duration_s', 'rate_hz', 'frames',
                  'cameras', 'action_kind', 'action_frame', 'rear_gap_requested_m',
                  'diagnostic_deceleration_mps2')
    if any(early_config.get(key) != late_config.get(key) for key in fixed_keys):
        raise ValueError('Fixed construction policy differs')
    if action != early_config['action_kind'] or action != late_config['action_kind']:
        raise ValueError('Wrong action comparison')
    if early_config['signal_command_frame'] >= late_config['signal_command_frame']:
        raise ValueError('Declared signal-time variable does not differ')
    action_key = ('first_observed_stop_frame' if action == 'stop' else
                  'first_diagnostic_3mps2_deceleration_frame')
    action_frame = early.get(action_key)
    if action_frame is None or late.get(action_key) != action_frame:
        raise ValueError('Fixed observed action timing differs')
    early_signal = early.get('first_observed_signal_frame')
    late_signal = late.get('first_observed_signal_frame')
    if early_signal is None or late_signal is None or not (
            early_signal < action_frame <= late_signal):
        raise ValueError('Requested before/after signal distinction absent')
    return {'format': 'c179480-rear-signal-comparison-audit-v1',
            'action_kind': action, 'observed_action_frame': action_frame,
            'observed_early_signal_frame': early_signal,
            'observed_late_signal_frame': late_signal,
            'fixed_motion_and_rear_source': True,
            'raw_signal_order_difference_observed': True,
            'legal_appropriateness_claimed': False,
            'physical_acceptance_claimed': False}


def bundled_config(suffix):
    bundle = json.loads((HERE / 'native' / 'bundles' / suffix / 'construction.json').read_text())
    return json.loads(next(item['content'] for item in bundle['files']
                           if item['path'] == 'config.json'))


def self_test():
    results = []
    for action, suffixes in (('stop', ('witness_1', 'witness_2')),
                             ('sudden_decrease', ('decrease_early', 'decrease_late'))):
        first, second = suffixes
        early = measure(HERE / 'selected-source' / first, HERE.name + '__' + first)
        late = measure(HERE / 'selected-source' / second, HERE.name + '__' + second)
        configs = [bundled_config(suffix) for suffix in suffixes]
        proof = compare(early, late, *configs, action)
        changed = dict(late, fixed_motion_sha256='0' * 64)
        try:
            compare(early, changed, *configs, action)
        except ValueError as error:
            assert 'Fixed actor motion' in str(error)
        else:
            raise AssertionError('Changed fixed motion accepted')
        changed = dict(late, source_sha256={})
        try:
            compare(early, changed, *configs, action)
        except ValueError as error:
            assert 'source hashes' in str(error)
        else:
            raise AssertionError('Missing camera source accepted')
        results.append(proof)
    return {'synthetic_cpu_test_passed': True, 'comparisons': results,
            'original_native_observed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--early', type=Path)
    parser.add_argument('--late', type=Path)
    parser.add_argument('--action', choices=('stop', 'sudden_decrease'))
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        value = self_test()
    else:
        if args.early is None or args.late is None or args.action is None:
            parser.error('Original early/late attempt paths and action are required')
        early_config = json.loads((args.early / 'config.json').read_text())
        late_config = json.loads((args.late / 'config.json').read_text())
        value = compare(measure(args.early, early_config['case_id'],
                                source_kind='original_native'),
                        measure(args.late, late_config['case_id'],
                                source_kind='original_native'),
                        early_config, late_config, args.action)
    print(json.dumps(value, sort_keys=True))
