"""Compare original-shaped signal histories at fixed motion conditions."""

import copy
import hashlib
import json
from pathlib import Path

from signal_advance_audit import measure

ROOT = Path(__file__).resolve().parent
CASES = ('signal_advance_100_below_25', 'signal_advance_100_at',
         'signal_advance_100_above_36')
TARGETS = (25.0, 30.48, 36.0)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def motion_without_indicator(rows):
    return [{key: value for key, value in row.items() if key != 'ego_left_indicator'}
            for row in rows]


def main():
    histories = []
    evidence = []
    for name, target in zip(CASES, TARGETS):
        source = ROOT / 'cases' / name / 'diagnostic.json'
        diagnostic = json.loads(source.read_text())
        rows = [json.loads(line) for line in
                diagnostic['files']['interaction_history.jsonl'].splitlines() if line]
        require(len(rows) == 210, 'Comparison needs all original-shaped frames')
        observed = measure(rows)
        value = observed['observed_continuous_approach_distance_m']
        require(abs(value - target) < .05 and
                observed['probes']['30.48']['observable_distance_met'] == (target >= 30.48)
                and observed['probes']['30.48']['full_signal_onset_observed'] is True
                and observed['legal_verdict_asserted'] is False,
                'Source-measured boundary result differs')
        histories.append(rows)
        evidence.append({'case_id': ROOT.name + '__' + name,
                         'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                         'authored_target_m': target, 'measured_m': value,
                         'continuous_start_frame': observed['continuous_start_frame'],
                         'observable_30_48_m_met': target >= 30.48})
    base = motion_without_indicator(histories[1])
    require(all(motion_without_indicator(rows) == base for rows in histories),
            'A non-signal source condition changed')
    require(all(left['measured_m'] < right['measured_m']
                for left, right in zip(evidence, evidence[1:])),
            'Observed signal onset does not increase across probes')
    mutated = copy.deepcopy(histories[0])
    mutated[80]['oncoming']['position_xy_m'][0] += 1.0
    require(motion_without_indicator(mutated) != base,
            'Changed opposing position passed fixed-condition check')
    print(json.dumps({'format': 'worker-signal-distance-fixed-condition-comparison',
                      'cases': evidence, 'fixed_motion_except_indicator': True,
                      'changed_opposing_position_rejected': True,
                      'source_kind': 'synthetic software diagnostics',
                      'native_or_legal_acceptance_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
