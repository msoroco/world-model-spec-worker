"""Independent original-source comparisons for C158208 yield cases."""

import argparse
import hashlib
import json
from pathlib import Path

from worker_exchange.measurement_contract import verify_report


ROOT = Path(__file__).resolve().parent
PREFIX = 'testing__C158208__NRS-484B-257-1__motor_vehicle_driver__'
GROUPS = {
    'ego_response': ('yield_nearest_slowed', 'yield_nearest_stopped',
                     'yield_nearest_unchanged_speed'),
    'through_timing': ('yield_nearest_through_occupied',
                       'yield_nearest_through_approaching'),
}
FIXED = ('road.xodr', 'road_context.json', 'control_context.json',
         'capture/native_map_facts.json', 'video_frames.jsonl')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit(attempts, comparison):
    if comparison not in GROUPS:
        raise ValueError('Unknown C158208 comparison')
    roots = tuple(Path(path) for path in attempts)
    expected = tuple(PREFIX + suffix for suffix in GROUPS[comparison])
    if len(roots) != len(expected):
        raise ValueError('Comparison requires every selected exact case')
    configs = tuple(read(root / 'config.json') for root in roots)
    if tuple(config.get('selected_case_id') for config in configs) != expected:
        raise ValueError('Comparison selected another exact case or order')
    for config in configs:
        if (config.get('law_id'), config.get('cell_id'), config.get('actor'),
                config.get('rate_hz'), config.get('duration_s')) != (
                'NRS-484B-257-1', 'C158208', 'motor_vehicle_driver', 20, 30):
            raise ValueError('Comparison capture profile changed')
    for name in ('cameras', 'required_atoms', 'source_packets'):
        if any(config[name] != configs[0][name] for config in configs[1:]):
            raise ValueError('Fixed comparison contract changed: ' + name)
    for name in FIXED:
        if any(sha(root / name) != sha(roots[0] / name) for root in roots[1:]):
            raise ValueError('Fixed comparison source changed: ' + name)
    contract = read(ROOT / 'measurement-contract.json')
    reports = tuple(read(root / 'analysis-report.json') for root in roots)
    histories = tuple(rows(root / 'interaction_history.jsonl') for root in roots)
    for root, report, history in zip(roots, reports, histories):
        if (len(verify_report(contract, report, root)) != 7
                or report.get('legal_conclusion') != 'unresolved'
                or len(history) != 600):
            raise ValueError('Comparison lacks full original-source measurements')
    if comparison == 'ego_response':
        if any([row.get('through') for row in history] !=
               [row.get('through') for row in histories[0]] for history in histories[1:]):
            raise ValueError('Through traffic changed in response comparison')
        if any(history[0]['ego']['body_vertices_m'] !=
               histories[0][0]['ego']['body_vertices_m'] for history in histories[1:]):
            raise ValueError('Initial ego position changed in response comparison')
        speeds = [report['measurements']['speed_at_closest_view_mps']['value']
                  for report in reports]
        if speeds != [2.0, 0.0, 8.0]:
            raise ValueError('Response sweep lacks measured slowed/stopped/unchanged cases')
        observed = {'closest_view_speeds_mps': speeds}
    else:
        if [row['ego'] for row in histories[0]] != [row['ego'] for row in histories[1]]:
            raise ValueError('Ego motion changed in through-traffic comparison')
        entry = [report['measurements']['yield_relation']['value']
                 ['through_intersection_entry_frame'] for report in reports]
        if not all(isinstance(frame, int) for frame in entry) or not entry[0] < entry[1]:
            raise ValueError('Through-traffic entry timing did not vary as planned')
        observed = {'through_entry_frames': entry}
    return {'format': 'worker-c158208-independent-source-comparison',
            'comparison': comparison, 'case_ids': list(expected),
            'fixed_source_sha256': {name: sha(roots[0] / name) for name in FIXED},
            'analysis_sha256': [sha(root / 'analysis-report.json') for root in roots],
            'interaction_sha256': [sha(root / 'interaction_history.jsonl') for root in roots],
            'observed': observed, 'software_comparison_passed': True,
            'physical_acceptance_claimed': False, 'legal_conclusion': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--attempt', type=Path, action='append', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.comparison), indent=2))


if __name__ == '__main__':
    main()
