"""Independent saved-source comparison for one signed right/left pair."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from geometry import TURN_FIRST_FRAME
from saved_native import assess_geometry, audit_attempt, rows


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assess_pair(obey_native, turn_native, obey_config, turn_config, obey_survey, turn_survey):
    if obey_config['behavior'] != 'obey' or turn_config['behavior'] != 'turn':
        raise ValueError('Signed-turn pair behavior differs')
    fixed = ('direction', 'cell_id', 'law_id', 'actor', 'sign_code', 'rate_hz',
             'duration_s', 'road_sha256')
    if any(obey_config[k] != turn_config[k] for k in fixed):
        raise ValueError('Signed-turn controlled fixed condition differs')
    if obey_survey != turn_survey:
        raise ValueError('Signed-turn live approach/sign survey differs')
    if len(obey_native) != len(turn_native) or len(obey_native) != 600:
        raise ValueError('Signed-turn comparison frame inventory differs')
    for a, b in zip(obey_native[:TURN_FIRST_FRAME+1],
                    turn_native[:TURN_FIRST_FRAME+1]):
        if math.dist(a['native_center_xy_m'], b['native_center_xy_m']) > .5:
            raise ValueError('Signed-turn observed approach differs')
        if a['native_road_id'] != b['native_road_id']:
            raise ValueError('Signed-turn observed approach road differs')
    obey = assess_geometry(obey_native, obey_config)
    turn = assess_geometry(turn_native, turn_config)
    if obey['destination_road_id'] == turn['destination_road_id']:
        raise ValueError('Signed-turn observed destinations are not distinct')
    return {'format': 'c104538-staged-signed-turn-comparison-v1',
            'cell_id': obey_config['cell_id'], 'law_id': obey_config['law_id'],
            'direction': obey_config['direction'], 'passed': True,
            'fixed_approach_frames': TURN_FIRST_FRAME+1,
            'observed_obey': obey, 'observed_turn': turn,
            'official_sign_authorization_verified': False,
            'rider_posture_verified': False, 'legal_verdict_claimed': False,
            'accepted': False}


def audit_pair(obey_attempt, turn_attempt):
    obey_attempt, turn_attempt = Path(obey_attempt), Path(turn_attempt)
    obey_review, turn_review = audit_attempt(obey_attempt), audit_attempt(turn_attempt)
    obey_config = json.loads((obey_attempt / 'config.json').read_text())
    turn_config = json.loads((turn_attempt / 'config.json').read_text())
    obey_survey = json.loads((obey_attempt / 'sign-survey.json').read_text())
    turn_survey = json.loads((turn_attempt / 'sign-survey.json').read_text())
    comparison = assess_pair(rows(obey_attempt / 'native_samples.jsonl'),
                             rows(turn_attempt / 'native_samples.jsonl'),
                             obey_config, turn_config, obey_survey, turn_survey)
    comparison['case_ids'] = [obey_config['case_id'], turn_config['case_id']]
    comparison['review_sha256'] = [hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
                                    for value in (obey_review, turn_review)]
    comparison['original_native_source_sha256'] = [
        sha(obey_attempt / 'native_samples.jsonl'),
        sha(turn_attempt / 'native_samples.jsonl')]
    return comparison


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--obey-attempt', required=True)
    parser.add_argument('--turn-attempt', required=True)
    args = parser.parse_args()
    print(json.dumps(audit_pair(args.obey_attempt, args.turn_attempt), sort_keys=True))
