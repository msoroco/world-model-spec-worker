"""Independent original-source comparison of the C158190 case pairs."""

import argparse
import hashlib
import json
from pathlib import Path

from worker_exchange.measurement_contract import verify_report

ROOT = Path(__file__).resolve().parent
PREFIX = 'testing__C158190__NRS-484B-257-1__motor_vehicle_driver__yield_nearest_view_'
PAIRS = {
    'approaching_traffic_vs_clear': ('through_approaches', 'clear'),
    'slowed_vs_no_slow': ('through_approaches', 'no_slow'),
    'approaching_vs_already_entered': ('through_approaches', 'through_entered'),
    'same_approaching_traffic_view_speed_2_vs_4': ('through_approaches', 'mid_speed'),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def same_support_logic(left, right, name):
    """Permit only the audited extension that registers the fifth case ID."""
    old, new = ((root / name).read_text() for root in (left, right))
    if name == 'runner.py':
        new = new.replace(
            "'yield_nearest_view_clear', 'yield_nearest_view_no_slow',\n            'yield_nearest_view_mid_speed')",
            "'yield_nearest_view_clear', 'yield_nearest_view_no_slow')")
        new = new.replace(
            "    supported = [PREFIX + suffix for suffix in SUFFIXES]\n"
            "    declared = config.get('supported_case_ids')\n"
            "    if case_id == PREFIX + 'yield_nearest_view_mid_speed':\n"
            "        valid = declared == supported\n"
            "    else:\n"
            "        valid = declared in (supported, supported[:-1])\n"
            "    if not valid:\n"
            "        raise ValueError('Selected case support list differs')",
            "    if config.get('supported_case_ids') != [PREFIX + suffix for suffix in SUFFIXES]:\n"
            "        raise ValueError('Four exact case IDs required')")
    elif name == 'yield_controller.py':
        new = new.replace(
            "'yield_nearest_view_no_slow',\n                   'yield_nearest_view_mid_speed')",
            "'yield_nearest_view_no_slow')")
    return old == new


def audit(left, right, comparison_id):
    if comparison_id not in PAIRS:
        raise ValueError('Unknown C158190 comparison')
    left, right = Path(left), Path(right)
    expected = tuple(PREFIX + suffix for suffix in PAIRS[comparison_id])
    configs = [read(root / 'config.json') for root in (left, right)]
    if tuple(config['selected_case_id'] for config in configs) != expected:
        raise ValueError('Comparison selected another exact case pair')
    for config in configs:
        if (config.get('law_id'), config.get('cell_id'), config.get('rate_hz'),
                config.get('duration_s')) != ('NRS-484B-257-1', 'C158190', 20, 30):
            raise ValueError('Comparison capture profile changed')
    if configs[0]['cameras'] != configs[1]['cameras']:
        raise ValueError('Fixed source-camera profile changed')
    speed_pair = comparison_id == 'same_approaching_traffic_view_speed_2_vs_4'
    for name in ('road.xodr', 'road_context.json', 'control_context.json',
                 'capture/native_map_facts.json', 'runner.py', 'yield_controller.py',
                 'video_frames.jsonl'):
        if speed_pair and name in ('runner.py', 'yield_controller.py'):
            fixed = same_support_logic(left, right, name)
        else:
            fixed = sha(left / name) == sha(right / name)
        if not fixed:
            raise ValueError('Fixed comparison source changed: ' + name)
    contract = read(ROOT / 'measurement-contract.json')
    reports = [read(root / 'analysis-report.json') for root in (left, right)]
    for root, report in zip((left, right), reports):
        verified = verify_report(contract, report, root)
        if len(verified) != 7:
            raise ValueError('Comparison lacks seven source-bound measurements')
    bodies = [rows(root / 'interaction_history.jsonl') for root in (left, right)]
    if any(len(item) != 600 for item in bodies):
        raise ValueError('Comparison lacks full original body histories')
    speeds = [report['measurements']['speed_at_closest_view_mps']['value']
              for report in reports]
    if comparison_id == 'approaching_traffic_vs_clear':
        if (not all(row.get('through') for row in bodies[0])
                or any(row.get('through') is not None for row in bodies[1])
                or speeds != [2.0, 4.0]):
            raise ValueError('Approaching versus clear source difference absent')
    elif comparison_id == 'slowed_vs_no_slow':
        if (not all(row.get('through') for rows_ in bodies for row in rows_)
                or any(bodies[0][0]['through'].get(key) != bodies[1][0]['through'].get(key)
                       for key in ('road_id', 'lane_id', 'body_vertices_m'))
                or speeds != [2.0, 6.0]):
            raise ValueError('Slowed versus no-slow source difference absent')
    elif comparison_id == 'same_approaching_traffic_view_speed_2_vs_4':
        if (speeds != [2.0, 4.0]
                or not all(row.get('through') for rows_ in bodies for row in rows_)
                or any(a['through'] != b['through'] for a, b in zip(*bodies))):
            raise ValueError('Same-traffic speed source difference absent')
    else:
        if (bodies[0][0]['through']['road_id'] != 158194
                or bodies[1][0]['through']['road_id'] != 158195
                or speeds != [2.0, 2.0]):
            raise ValueError('Approaching versus entered source difference absent')
    return {'format': 'worker-c158190-independent-comparison-audit',
            'comparison_id': comparison_id, 'case_ids': list(expected),
            'fixed_source_hashes': {name: sha(left / name) for name in
                                    ('road.xodr', 'road_context.json',
                                     'control_context.json', 'capture/native_map_facts.json',
                                     'runner.py', 'yield_controller.py',
                                     'video_frames.jsonl')},
            'case_support_extension_only': speed_pair,
            'right_support_source_hashes': ({name: sha(right / name) for name in
                                             ('runner.py', 'yield_controller.py')}
                                            if speed_pair else {}),
            'analysis_sha256': [sha(root / 'analysis-report.json') for root in (left, right)],
            'actor_history_sha256': [sha(root / 'interaction_history.jsonl')
                                     for root in (left, right)],
            'closest_view_speeds_mps': speeds,
            'software_comparison_passed': True,
            'physical_acceptance_claimed': False,
            'legal_conclusion': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    parser.add_argument('--comparison', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.left, args.right, args.comparison), indent=2))


if __name__ == '__main__':
    main()
