"""Engineering fallback routing from source-bound saved passing observations."""
import json
from pathlib import Path

from measure_pass import measure

FALLBACKS = ('fallback1', 'fallback2', 'fallback3')
DISTANCES = (70, 120, 170)


def evaluate(distance, candidate, saved_folder, expected_hashes=None):
    if distance not in DISTANCES or candidate not in FALLBACKS:
        raise ValueError('Unknown exact passing case or fallback')
    measurement = measure(Path(saved_folder), expected_hashes)
    if candidate == 'fallback1':
        metric = measurement['entry_oncoming_body_gap_m']
        threshold = 100.0
        triggered = metric < threshold
        reason = 'measured entry oncoming body gap below engineering review threshold'
    elif candidate == 'fallback2':
        metric = measurement['minimum_pre_return_oncoming_body_gap_m']
        threshold = 20.0
        triggered = metric < threshold
        reason = 'measured minimum pre-return body gap below engineering review threshold'
    else:
        metric = measurement['all_left_phase_sightline_flags_visible']
        threshold = True
        triggered = not metric
        reason = 'saved driver-eye visibility flag missing during left-of-center phase'
    return {'format': 'c102951-measured-fallback-trigger-v1',
            'case_id': Path(__file__).resolve().parent.parent.name+'__'+str(distance),
            'candidate_id': candidate, 'source_kind': measurement['source_kind'],
            'source_hashes': measurement['source_hashes'], 'triggered': triggered,
            'metric': metric, 'threshold': threshold, 'reason': reason,
            'engineering_routing_only': True, 'safe_distance_judgment': None,
            'interference_judgment': None, 'legal_verdict': None,
            'delivery_ready': False}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('distance', type=int, choices=DISTANCES)
    parser.add_argument('candidate', choices=FALLBACKS)
    parser.add_argument('saved_folder', type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.distance, args.candidate, args.saved_folder), indent=2))
