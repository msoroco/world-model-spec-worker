"""Sealed 900-frame CPU signal-distance contrasts for both statutory probes.

This tests source measurement only. It is not an exact-case compatibility,
saved-processing, delivery, Native-motion or legal proof.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
ASSIGNMENT = FOLDER.parents[1]
sys.path.insert(0, str(ASSIGNMENT))
from signal_advance_audit import audit
from signal_advance_native_probe import PROBES_M


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def build(root, *, target_m, interrupted=False):
    if root.exists():
        raise ValueError('Use a fresh ignored fixture root')
    root.mkdir(parents=True)
    warmup = 32
    signal_steps = math.ceil(target_m / 0.25)
    step = target_m / signal_steps
    turn_index = warmup + signal_steps + 1
    rows = []
    for index in range(900):
        if index < turn_index:
            xy = [round((index - warmup - signal_steps) * step, 9), 0.0]
            heading = 0.0
        else:
            xy = [0.0, round(-0.25 * min(index - turn_index + 1, 20), 9)]
            heading = -20.0 if index == turn_index else -90.0
        indicator = warmup <= index <= turn_index
        if interrupted and index == warmup + signal_steps // 2:
            indicator = False
        rows.append({
            'frame': 50000 + index,
            'time_s': round((index + 1) / 20, 6),
            'ego': {'position_xy_m': xy},
            'ego_heading_deg': heading,
            'ego_left_indicator': indicator,
        })
    source = root / 'interaction_history.jsonl'
    source.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
    write(root / 'capture-seal.json', {
        'format': 'worker-sealed-capture',
        'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True,
        'frames': 900,
        'sources': {source.name: sha(source)},
        'physical_acceptance_claimed': False,
    })
    return audit(root)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    root = args.output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    results = []
    for target in PROBES_M:
        branch = str(target).replace('.', '_')
        result = build(root / branch, target_m=target)
        threshold = 30.48 if target < 50 else 91.44
        observed = result['observed_continuous_approach_distance_m']
        if abs(observed - target) > 1e-5:
            raise ValueError('Source-distance path differs from declared probe')
        if result['probes'][str(threshold)]['observable_distance_met'] != (target >= threshold):
            raise ValueError('Below/at/above source classification differs')
        if not result['probes'][str(threshold)]['full_signal_onset_observed']:
            raise ValueError('Signal onset not retained in original source')
        results.append({'target_m': target, 'threshold_m': threshold,
                        'history_sha256': result['history_sha256'],
                        'capture_seal_sha256': result['capture_seal_sha256'],
                        'observed_m': observed,
                        'threshold_observable_met': target >= threshold,
                        'diagnostic_fixture': True,
                        'legal_verdict_asserted': False})
    interrupted = build(root / 'interrupted', target_m=36.0, interrupted=True)
    if interrupted['probes']['30.48']['observable_distance_met']:
        raise ValueError('Interrupted indicator was accepted at 30.48 m')
    tampered = root / 'interrupted' / 'interaction_history.jsonl'
    tampered.write_text(tampered.read_text() + '\n')
    try:
        audit(root / 'interrupted')
    except ValueError as error:
        if 'capture seal' not in str(error):
            raise
    else:
        raise ValueError('Changed original history was accepted')
    print(json.dumps({'format': 'worker-signal-distance-diagnostic',
                      'frames_per_branch': 900, 'results': results,
                      'interrupted_rejected': True, 'changed_seal_rejected': True,
                      'software_checks_passed': True,
                      'physical_acceptance_claimed': False,
                      'legal_verdict_asserted': False}, sort_keys=True))


if __name__ == '__main__':
    main()
