"""CPU proof for the three exact 600-frame Native construction requests."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import copy

from construction import HERE, check_comparisons, check_map, proposal
from control import check as check_controller, command
from runner import check as check_runner

ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reject(call, expected):
    try:
        call()
    except ValueError as exc:
        if expected not in str(exc):
            raise AssertionError(f'Wrong rejection: {exc}') from exc
        return str(exc)
    raise AssertionError(f'Missing rejection: {expected}')


def main():
    output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    if ROOT / '.runtime-work' not in output_root.parents:
        raise ValueError('Set output root under .runtime-work before proving')
    comparisons = check_comparisons()
    controller = check_controller()
    config = json.loads((HERE / 'config.json').read_text())
    runner = check_runner(config)
    plans = {suffix: proposal(suffix) for suffix in ('probe_1', 'probe_2',
                                                     'permission_before_entry')}
    traces = {suffix: [command(suffix, frame) for frame in range(600)]
              for suffix in plans}
    positives = {
        'wait_zero_speed_frames': sum(row['pedestrian_speed_mps'] == 0
                                      for row in traces['probe_1']),
        'early_active_frames': sum(row['pedestrian_speed_mps'] > 0
                                   for row in traces['probe_2']),
        'permission_active_frames': sum(row['requested_other_device_permission']
                                        for row in traces['permission_before_entry']),
        'same_entry_trajectory': [row['pedestrian_speed_mps'] for row in traces['probe_2']] ==
                                 [row['pedestrian_speed_mps'] for row in traces['permission_before_entry']],
    }
    if positives != {'wait_zero_speed_frames': 600, 'early_active_frames': 480,
                     'permission_active_frames': 500, 'same_entry_trajectory': True}:
        raise AssertionError('Controlled source trace changed')
    negatives = {
        'unknown_case': reject(lambda: proposal('invented_case'), 'Unknown exact'),
        'negative_frame': reject(lambda: command('probe_2', -1), 'outside 600-frame'),
        'end_frame': reject(lambda: command('probe_2', 600), 'outside 600-frame'),
    }
    wrong = copy.deepcopy(config)
    wrong['requested_walker_move_start_frame'] = 100
    negatives['wrong_runner_schedule'] = reject(lambda: check_runner(wrong),
                                                'Exact permission or entry schedule differs')
    with tempfile.TemporaryDirectory(prefix='c111334-map-', dir=ROOT / '.runtime-work') as directory:
        altered = Path(directory) / 'road.xodr'
        altered.write_text((HERE / 'road.xodr').read_text().replace(
            'C111334-facing-green-turn-arrow', 'C111334-unnamed-head'))
        negatives['missing_arrow_head'] = reject(lambda: check_map(altered),
                                                  'Two distinct named signal objects required')
    receipt = {
        'format': 'c111334-native-construction-cpu-proof-v1',
        'comparison_check': comparisons, 'controller_check': controller,
        'runner_check': runner,
        'planned_cases': plans, 'positives': positives, 'negatives': negatives,
        'road_sha256': sha(HERE / 'road.xodr'),
        'construction_script_sha256': sha(HERE / 'construction.py'),
        'control_script_sha256': sha(HERE / 'control.py'),
        'runner_script_sha256': sha(HERE / 'runner.py'),
        'signal_script_sha256': sha(HERE / 'signals.py'),
        'primary_config_sha256': sha(HERE / 'config.json'),
        'native_executed': False, 'physical_signal_pixels_observed': False,
        'other_device_authority_observed': False, 'legal_verdict_claimed': False,
        'delivery_ready': False,
    }
    target = HERE / 'construction-cpu-proof.json'
    target.write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'positive_count': len(positives), 'negative_count': len(negatives),
                      'frames_per_case': 600, 'proof_sha256': sha(target)}))


if __name__ == '__main__':
    main()
