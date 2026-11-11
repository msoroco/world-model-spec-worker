"""Measure observed continuous left-indicator distance from sealed Native history.

NRS 484B.253 refers to a signal given when and as required. The 30.48 m and
91.44 m probes come from the separate turn-signal rule; this module makes no
finding about district classification, signal adequacy, or legal duty.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

PROBES_M = (30.48, 91.44)


def measure(history, *, probes_m=PROBES_M):
    if len(history) < 2:
        raise ValueError('At least two original samples required')
    first_heading = history[0].get('ego_heading_deg')
    if type(first_heading) not in (int, float) or not math.isfinite(first_heading):
        raise ValueError('Missing initial heading')
    prior_frame = prior_time = None
    positions = []
    for row in history:
        frame, time = row.get('frame'), row.get('time_s')
        position = row.get('ego', {}).get('position_xy_m')
        if (type(frame) is not int or type(time) not in (int, float) or
                not math.isfinite(time) or (prior_frame is not None and
                (frame != prior_frame + 1 or time <= prior_time))):
            raise ValueError('Nonconsecutive original frame/time')
        if (not isinstance(position, list) or len(position) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in position)):
            raise ValueError('Missing original ego position')
        heading = row.get('ego_heading_deg')
        if type(heading) not in (int, float) or not math.isfinite(heading):
            raise ValueError('Missing original ego heading')
        if type(row.get('ego_left_indicator')) is not bool:
            raise ValueError('Missing original indicator readback')
        positions.append(position)
        prior_frame, prior_time = frame, time
    turn_index = next((i for i, row in enumerate(history)
                       if abs((row['ego_heading_deg'] - first_heading + 180) % 360 - 180) >= 15), None)
    if turn_index is None:
        raise ValueError('No observed left-turn course change')
    # The turn sample is excluded: only the original approach before course
    # change can establish advance signalling.
    continuous_start = turn_index
    if history[turn_index]['ego_left_indicator']:
        while continuous_start > 0 and history[continuous_start - 1]['ego_left_indicator']:
            continuous_start -= 1
    distance = sum(math.dist(positions[i - 1], positions[i])
                   for i in range(continuous_start + 1, turn_index + 1))
    # A true indicator at capture start establishes a lower bound only; the
    # beginning of the signal may have preceded the retained source.
    starts_at_capture = continuous_start == 0 and history[0]['ego_left_indicator']
    return {
        'turn_frame': history[turn_index]['frame'],
        'continuous_start_frame': (history[continuous_start]['frame']
                                   if continuous_start < turn_index else None),
        'observed_continuous_approach_distance_m': distance,
        'signal_active_at_capture_start': starts_at_capture,
        'probes': {str(probe): {'observable_distance_met': distance >= probe,
                                'full_signal_onset_observed': continuous_start < turn_index and not starts_at_capture}
                   for probe in probes_m},
        'district_classification': 'unresolved',
        'legal_verdict_asserted': False,
    }


def audit(attempt):
    root = Path(attempt)
    seal = json.loads((root / 'capture-seal.json').read_text())
    path = root / 'interaction_history.jsonl'
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if seal.get('sources', {}).get(path.name) != digest:
        raise ValueError('Original history is absent from current capture seal')
    history = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    result = measure(history)
    result['history_sha256'] = digest
    result['capture_seal_sha256'] = hashlib.sha256((root / 'capture-seal.json').read_bytes()).hexdigest()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('attempt')
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt), indent=2, sort_keys=True))
