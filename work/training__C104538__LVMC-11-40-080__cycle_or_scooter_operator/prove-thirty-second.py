"""Prove the long-window rider timing plan without claiming physical movement."""
import copy
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from thirty_second import KINDS, VARIANTS, digest, rows, validate


def rejected(source, kind, candidate, expected):
    try:
        validate(source, kind, candidate)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError('Unexpected rejection: ' + str(error))
        return str(error)
    raise AssertionError('Invalid long-window rider plan passed')


def main():
    records = []
    for candidate in VARIANTS:
        sources = {kind: rows(kind, candidate) for kind in KINDS}
        for kind, source in sources.items():
            measurement = validate(source, kind, candidate)
            if kind != 'mounted_obey' and measurement['post_turn_frames'] < 290:
                raise AssertionError('Long-window post-turn observation too short')
            records.append({'kind': kind, 'candidate': candidate,
                            'source_sha256': digest(source), **measurement})
        release = VARIANTS[candidate]['turn_start_frame']
        obey, turn, dismounted = (sources[kind] for kind in KINDS)
        if any(a != b for a, b in zip(obey[:release], turn[:release])):
            raise AssertionError('Controlled mounted approaches differ before release')
        if any((a['x_m'], a['y_m']) != (b['x_m'], b['y_m']) for a, b in zip(turn, dismounted)):
            raise AssertionError('Dismount control changed requested route')
    baseline = rows('dismounted_turn', 'primary')
    negatives = {}
    changed = copy.deepcopy(baseline)
    changed.pop()
    negatives['short_capture'] = rejected(changed, 'dismounted_turn', 'primary', 'frame inventory')
    changed = copy.deepcopy(baseline)
    changed[300]['time_s'] += .05
    negatives['time_skew'] = rejected(changed, 'dismounted_turn', 'primary', 'timebase')
    changed = copy.deepcopy(baseline)
    changed[220]['mounted'] = True
    changed[220]['walking_machine'] = False
    negatives['remounted_turn'] = rejected(changed, 'dismounted_turn', 'primary', 'persist')
    changed = copy.deepcopy(baseline)
    changed[4]['sign_id'] = 'unrelated-head'
    negatives['wrong_sign'] = rejected(changed, 'dismounted_turn', 'primary', 'identity')
    proof = {'format': 'c104538-rider-long-window-cpu-proof-v1',
             'rate_hz': 20, 'duration_s': 30, 'frames': 600,
             'records': records, 'controlled_pairs_checked': 4,
             'dismount_controls_checked': 4, 'rejected_negatives': negatives,
             'physical_sign_authorization_proven': False,
             'original_rider_posture_observed': False,
             'native_executed': False, 'selected': False, 'accepted': False}
    path = HERE / 'thirty-second-proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'variants': len(records), 'controlled_pairs': 4,
                      'negative_rejections': len(negatives), 'native_executed': False}))


if __name__ == '__main__':
    main()
