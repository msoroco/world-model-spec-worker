"""CPU-only comparison audit wiring and fixed-condition rejection."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from comparison_audit import COMPARISONS, WORK, audit
from signal_approach import ASSIGNMENT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', choices=COMPARISONS, required=True)
    parser.add_argument('--mode', choices=('positive', 'changed_fixed'), required=True)
    parser.add_argument('--scratch', required=True)
    args = parser.parse_args()
    scratch = Path(args.scratch).resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as folder:
        paths = {}
        for case_id in COMPARISONS[args.comparison]['case_ids']:
            short = case_id.removeprefix(ASSIGNMENT + '__')
            path = WORK / ('config.json' if short == 'approach_below_30ft_park'
                           else 'cases/' + short + '/config.json')
            config = json.loads(path.read_text(encoding='utf-8'))
            case = config['case']
            record = {'source_kind': 'synthetic_comparison_protocol',
                      'fixed_source_sha256': {'map': 'fixture-map',
                                               'highway': 'fixture-highway',
                                               'traffic': 'fixture-traffic'},
                      'camera_plan': config['cameras'],
                      'duration_s': config['duration_s'],
                      'measurement': {'case_id': case_id, 'frames': 900,
                                      'terminal_body_front_approach_gap_m':
                                          case['nominal_signal_distance_m']},
                      'approach_relation': case['approach_relation'],
                      'nominal_signal_distance_m': case['nominal_signal_distance_m'],
                      'activity': case['halt_activity'],
                      'signal_status': case['signal_status'],
                      'exception': case['exception_context']}
            report = {'format': 'worker-delivery-audit', 'assignment_id': ASSIGNMENT,
                      'case_id': case_id, 'passed': False,
                      'physical_acceptance_claimed': False,
                      'capture_seal_sha256': 'fixture-seal-'+short,
                      'video_sha256': 'fixture-video-'+short,
                      'comparison_record': record}
            output = Path(folder) / (short + '.json')
            output.write_text(json.dumps(report) + '\n', encoding='utf-8')
            paths[case_id] = output
        if args.mode == 'changed_fixed':
            target = paths[COMPARISONS[args.comparison]['case_ids'][1]]
            report = json.loads(target.read_text(encoding='utf-8'))
            report['comparison_record']['fixed_source_sha256']['map'] = 'changed-map'
            target.write_text(json.dumps(report) + '\n', encoding='utf-8')
            try:
                audit(args.comparison, paths, protocol_fixture=True)
            except ValueError as error:
                if 'fixed comparison condition differs: fixed_source_sha256' not in str(error):
                    raise
                print('Expected rejection:', error)
                return 2
            raise ValueError('changed fixed comparison map accepted')
        result = audit(args.comparison, paths, protocol_fixture=True)
        if result['passed'] is not False or result['physical_acceptance_claimed'] is not False:
            raise ValueError('CPU fixture claimed physical comparison acceptance')
        print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
