"""Original-source isolation checks for the two C126120 comparisons."""

import argparse
import hashlib
import json
from pathlib import Path

from worker_exchange.measurement_contract import verify_report

ROOT = Path(__file__).resolve().parent
PREFIX = 'testing__C126120__NRS-484B-227-1__motor_vehicle_driver__'
GROUPS = {
    'single_vs_multiple_uturn': ('source_verified_single_movement_uturn', 'source_verified_multiple_movement_uturn'),
    'opening_vs_divider_encroachment': ('source_verified_single_movement_uturn', 'divider_encroachment_before_opening_uturn'),
}
FIXED_SOURCES = ('road.xodr', 'diagnostic-site.json', 'divider_context.json',
                 'barrier_receipt.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(comparison, attempts):
    if comparison not in GROUPS or len(attempts) != 2:
        raise ValueError('Unknown or incomplete C126120 comparison')
    paths = [Path(p) for p in attempts]
    suffixes = GROUPS[comparison]
    configs = [read(p / 'config.json') for p in paths]
    if [c.get('selected_case_id') for c in configs] != [PREFIX + s for s in suffixes]:
        raise ValueError('Comparison selected another exact case or order')
    for config in configs:
        if (config.get('law_id'), config.get('cell_id'), config.get('actor'),
                config.get('rate_hz'), config.get('duration_s')) != (
                'NRS-484B-227-1', 'C126120', 'motor_vehicle_driver', 20, 30):
            raise ValueError('Comparison capture identity changed')
    for field in ('cameras', 'required_atoms', 'source_packets'):
        if configs[0][field] != configs[1][field]:
            raise ValueError('Fixed capture contract changed: ' + field)
    for source in FIXED_SOURCES:
        if sha(paths[0] / source) != sha(paths[1] / source):
            raise ValueError('Fixed site source changed: ' + source)
    histories = [rows(p / 'movement_history.jsonl') for p in paths]
    reports = [read(p / 'analysis-report.json') for p in paths]
    for suffix, path, history, report in zip(suffixes, paths, histories, reports):
        contract = read(ROOT / ('measurement-contract.json' if suffix == 'source_verified_single_movement_uturn'
                                else f'cases/{suffix}/measurement-contract.json'))
        if not verify_report(contract, report, path) or len(history) < 4:
            raise ValueError('Comparison lacks original selected measurements')
        if report.get('legal_conclusion') != 'unresolved':
            raise ValueError('Comparison presumes a legal conclusion')
    if [row.get('other_body_vertices_xy_m') for row in histories[0]] != [
            row.get('other_body_vertices_xy_m') for row in histories[1]]:
        raise ValueError('Other traffic changed in isolated comparison')
    if histories[0][0]['ego_body_vertices_xy_m'] != histories[1][0]['ego_body_vertices_xy_m']:
        raise ValueError('Initial right-hand-roadway body changed')
    angles = [report['measurements']['observed_turn_angle_degrees']['value'] for report in reports]
    overlap = [report['measurements']['any_body_overlap_outside_opening']['value'] for report in reports]
    gears = [[row.get('ego_gear') for row in history] for history in histories]
    if comparison == 'single_vs_multiple_uturn':
        if not (all(abs(angle) >= 150 for angle in angles) and overlap == [False, False]
                and set(gears[0]) == {'forward'} and 'reverse' in gears[1]):
            raise ValueError('Single versus multiple movement did not vary as planned')
    elif not (all(abs(angle) >= 150 for angle in angles) and overlap == [False, True]
              and all(set(sequence) == {'forward'} for sequence in gears)):
        raise ValueError('Opening versus divider encroachment did not vary as planned')
    return {'format': 'worker-c126120-independent-source-comparison',
            'comparison': comparison, 'case_ids': [PREFIX + s for s in suffixes],
            'fixed_source_sha256': {name: sha(paths[0] / name) for name in FIXED_SOURCES},
            'movement_sha256': [sha(p / 'movement_history.jsonl') for p in paths],
            'observed_angles_degrees': angles, 'observed_blocked_overlap': overlap,
            'software_comparison_passed': True, 'physical_acceptance_claimed': False,
            'legal_conclusion': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--attempt', action='append', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, args.attempt), indent=2))


if __name__ == '__main__':
    main()
