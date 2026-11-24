"""Positive and adversarial CPU proof for the near-event speed proposal."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from boundary_speed import (EVENT_SPEED_MPS, HZ, NORMAL_SPEED_MPS,
                            POSITION_ERROR_M, THRESHOLD_M, WINDOW_M,
                            bracket_budget, relation, target_speed)


def require(value, message):
    if not value:
        raise AssertionError(message)


def main():
    budget = bracket_budget()
    require(budget['one_foot_spacing_exceeds_budget'], 'Boundary spacing not resolved')
    require(abs(budget['maximum_two_event_interval_width_m'] - 0.28) < 1e-12,
            'Two-event source bracket budget differs')
    entry, turn = 10.0, 80.0
    for s in (entry - WINDOW_M, entry, entry + WINDOW_M,
              turn - WINDOW_M, turn, turn + WINDOW_M):
        require(target_speed(s, entry, turn) == EVENT_SPEED_MPS,
                'Near-event slowdown missing')
    require(target_speed(45, entry, turn) == NORMAL_SPEED_MPS,
            'Between-event travel speed differs')
    positives = {str(feet): relation(feet * .3048,
                 budget['maximum_two_event_interval_width_m'])
                 for feet in (199, 200, 201)}
    require(positives == {'199': 'within', '200': 'unresolved', '201': 'exceeds'},
            'Boundary probe relation differs')
    negatives = []
    normal = bracket_budget(NORMAL_SPEED_MPS, POSITION_ERROR_M)
    require(not normal['one_foot_spacing_exceeds_budget'],
            'Current 5 m/s speed incorrectly resolves one-foot spacing')
    negatives.append({'name': 'normal_speed_wide_brackets', 'budget': normal})
    for name, args in (('reversed_events', (20, 20, 15)),
                       ('nonfinite_station', (float('nan'), 10, 80))):
        try:
            target_speed(*args)
        except ValueError as error:
            negatives.append({'name': name, 'rejected_for': str(error)})
        else:
            raise AssertionError('Invalid route accepted: ' + name)
    for name, args in (('negative_position_error', (2.4, -0.1)),
                       ('zero_event_speed', (0.0, 0.02))):
        try:
            bracket_budget(*args)
        except ValueError as error:
            negatives.append({'name': name, 'rejected_for': str(error)})
        else:
            raise AssertionError('Invalid budget accepted: ' + name)
    proof = {'format': 'c394300-near-event-speed-cpu-proof-v1',
             'source_sha256': hashlib.sha256((HERE/'native/boundary_speed.py').read_bytes()).hexdigest(),
             'hz': HZ, 'baseline_speed_mps': NORMAL_SPEED_MPS,
             'proposed_event_speed_mps': EVENT_SPEED_MPS,
             'event_window_m': WINDOW_M, 'assumed_position_error_m': POSITION_ERROR_M,
             'budget': budget, 'synthetic_probe_relations': positives,
             'negatives': negatives, 'native_speed_observed': False,
             'actual_event_brackets_observed': False, 'physical_completion_verified': False}
    destination = HERE/'boundary-speed-proof.json'
    destination.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'probes': positives, 'negative_count': len(negatives)}))


if __name__ == '__main__':
    main()
