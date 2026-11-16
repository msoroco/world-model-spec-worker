"""Positive eight-request audit and controlled-pair negative CPU checks."""
import copy
import json
from pathlib import Path

import check

ROOT = Path(__file__).resolve().parents[1]


def prove():
    receipt = check.audit()
    rejected = []
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        folders = [ROOT/'native/drafts'/w/candidate for w in ('reference', 'contrast')]
        configs = [json.loads((folder/'config.json').read_text()) for folder in folders]
        tracks = [check.rows(folder/'requested-tracks.jsonl') for folder in folders]
        check.validate_pair(configs[0], tracks[0], configs[1], tracks[1])
        changed = copy.deepcopy(tracks[1])
        changed[100]['lead_x_m'] += 1
        try:
            check.validate_pair(configs[0], tracks[0], configs[1], changed)
        except ValueError as error:
            assert 'more than lateral clearance' in str(error)
            rejected.append(candidate+':lead_trajectory')
        else:
            raise AssertionError('Changed lead trajectory was accepted')
        changed_cfg = dict(configs[1], lead_requested_speed_mps=5)
        try:
            check.validate_pair(configs[0], tracks[0], changed_cfg, tracks[1])
        except ValueError as error:
            assert 'fixed config' in str(error)
            rejected.append(candidate+':lead_speed')
        else:
            raise AssertionError('Changed lead speed was accepted')
    return {'positive_candidates': receipt['candidates'],
            'negative_fixed_condition_rejections': rejected,
            'original_native_observed': False, 'legal_safety_verdict': None}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
