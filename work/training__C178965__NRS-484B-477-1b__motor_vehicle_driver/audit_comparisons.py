"""Audit the three diagnostic width contrasts against their selected drafts."""
import hashlib
import json
from pathlib import Path

from prove_alley import encoded, sample
from alley_measure import measure

HERE = Path(__file__).resolve().parent
ORDER = ('controlled_1', 'controlled_at_10', 'controlled_2')
EXPECTED = (3.9, 3.048, 2.4)


def read(path):
    return json.loads(path.read_text())


def config(suffix):
    construction = read(HERE / 'draft-alley' / suffix / 'primary' / 'construction.json')
    return json.loads(next(row['content'] for row in construction['files']
                           if row['path'] == 'config.json'))


def main():
    configs = [config(suffix) for suffix in ORDER]
    fixed = ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s', 'cameras',
             'required_atoms', 'source_packets', 'supported_case_ids')
    for key in fixed:
        if any(item[key] != configs[0][key] for item in configs[1:]):
            raise ValueError('Comparison changed fixed control: ' + key)
    widths = []
    for suffix, cfg in zip(ORDER, configs):
        if cfg['alley_case'] != suffix:
            raise ValueError('Selected case and controlled width differ')
        packet, inventory = sample({'controlled_1': 7.5,
                                    'controlled_at_10': 6.648,
                                    'controlled_2': 6.0}[suffix])
        measured = measure(encoded(packet), encoded(inventory))
        widths.append(measured['minimum_measured_halt_free_width_m'])
    if any(abs(actual - expected) > 1e-9 for actual, expected in zip(widths, EXPECTED)):
        raise ValueError('Diagnostic width does not match the exact boundary probe')
    if not widths[0] > 3.048 or widths[1] != 3.048 or not widths[2] < 3.048:
        raise ValueError('Less-than statutory boundary is not separated')
    plan = read(HERE / 'case-plan.json')
    pairs = {frozenset(row['case_ids']) for row in plan['comparisons']}
    case_ids = [cfg['case_id'] for cfg in configs]
    if pairs != {frozenset((case_ids[0], case_ids[1])),
                 frozenset((case_ids[0], case_ids[2])),
                 frozenset((case_ids[1], case_ids[2]))}:
        raise ValueError('Comparison plan omits a boundary pair')
    report = {'format': 'worker-diagnostic-comparison-audit-v1',
              'assignment_id': plan['assignment_id'],
              'case_ids': case_ids, 'source_kind': 'synthetic_fixture',
              'measured_free_widths_m': widths, 'threshold_m': 3.048,
              'fixed_controls': list(fixed), 'pairs_checked': 3,
              'physical_original_observed': False, 'legal_verdict_claimed': False,
              'passed': True}
    output = HERE / 'comparison-audit.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()},
                     sort_keys=True))


if __name__ == '__main__':
    main()
