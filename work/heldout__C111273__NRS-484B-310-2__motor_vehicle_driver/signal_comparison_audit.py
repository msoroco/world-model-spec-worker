"""Independent fixed-condition audit over saved C111273 original sources."""
import argparse
import hashlib
import json
from pathlib import Path

from flashing_yellow import CASES
from signal_finalizer import analyze


PAIRS = {
    'approach_speed_sample': ('east_cautious_approach', 'east_faster_approach',
                              {'approach_target_mps'}),
    'crossing_traffic_context': ('east_cautious_approach', 'east_clear_approach',
                                 {'crossing_vehicle'}),
    'approach_direction': ('east_cautious_approach', 'west_cautious_approach',
                           {'direction'}),
}


def _read(path):
    return json.loads(Path(path).read_text())


def audit(comparison_id, first, second):
    if comparison_id not in PAIRS:
        raise ValueError('Unknown frozen comparison')
    expected_a, expected_b, expected_diff = PAIRS[comparison_id]
    reports = [analyze(first, write_channels=False),
               analyze(second, write_channels=False)]
    if not reports[0]['case_id'].endswith('__'+expected_a) or not reports[1]['case_id'].endswith('__'+expected_b):
        raise ValueError('Wrong exact comparison cases')
    roots = [Path(first), Path(second)]
    configs = [_read(root/'config.json') for root in roots]
    contexts = [_read(root/'signal_context.json') for root in roots]
    if any(not context.get('junction_id') or not context.get('official_control_source')
           for context in contexts):
        raise ValueError('Missing fixed junction or control source')
    for key in ('junction_id', 'official_control_source', 'flash_period_s'):
        if contexts[0].get(key) != contexts[1].get(key):
            raise ValueError('Fixed condition differs: '+key)
    for key in ('rate_hz', 'frames', 'duration_s', 'cameras'):
        if configs[0].get(key) != configs[1].get(key):
            raise ValueError('Fixed condition differs: '+key)
    changed = {key for key, a, b in (
        ('approach_target_mps', CASES[expected_a].approach_target_mps,
         CASES[expected_b].approach_target_mps),
        ('crossing_vehicle', CASES[expected_a].crossing_vehicle,
         CASES[expected_b].crossing_vehicle),
        ('direction', CASES[expected_a].direction, CASES[expected_b].direction)) if a != b}
    if changed != expected_diff:
        raise ValueError('Declared case difference does not match exact cases')
    for config, branch in zip(configs, (expected_a, expected_b)):
        if config.get('target_speed_mps') != CASES[branch].approach_target_mps:
            raise ValueError('Requested speed differs from exact case')
    source_hashes = []
    for root, report in zip(roots, reports):
        hashes = report['measurements']['flashing_yellow']['source_hashes']
        for name, digest in hashes.items():
            if hashlib.sha256((root/name).read_bytes()).hexdigest() != digest:
                raise ValueError('Source changed during comparison audit')
        source_hashes.append(hashes)
    return {'format': 'worker-signal-comparison-audit',
            'comparison_id': comparison_id,
            'case_ids': [report['case_id'] for report in reports],
            'fixed_conditions_checked': True,
            'deliberate_differences': sorted(changed),
            'source_hashes': source_hashes,
            'legal_caution_judgment': 'unresolved',
            'physical_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--first', required=True)
    parser.add_argument('--second', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    path = Path(args.output)
    if path.exists(): raise ValueError('Retain prior comparison audit')
    path.write_text(json.dumps(audit(args.comparison, args.first, args.second),
                               indent=2)+'\n')


if __name__ == '__main__': main()
