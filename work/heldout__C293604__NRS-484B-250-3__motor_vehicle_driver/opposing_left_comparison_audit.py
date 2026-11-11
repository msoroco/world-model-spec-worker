"""Independent controlled comparison of planned left intent and observed turn."""

from hashlib import sha256
import json
from pathlib import Path

from opposing_left_measurement import measure_opposing_left


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(turn_attempt, hold_attempt):
    turn, hold = Path(turn_attempt), Path(hold_attempt)
    contexts = [json.loads((folder / 'opposing_left_context.json').read_text())
                for folder in (turn, hold)]
    if contexts[0] != contexts[1]:
        raise ValueError('Opposing-left planned route or actor context changed')
    for name in ('video_frames.jsonl', 'trace.jsonl'):
        if digest(turn / name) != digest(hold / name):
            raise ValueError('Opposing-left original frame or trace setup changed')
    first, second = (rows(folder / 'opposing_left_participants.jsonl')
                     for folder in (turn, hold))
    if not first or len(first) != len(second):
        raise ValueError('Opposing-left participant source length changed')
    fixed = ('frame', 'time_s', 'turning_actor_id', 'opposite_actor_id',
             'opposite_corners', 'opposite_heading_rad')
    for left, right in zip(first, second):
        if any(left[key] != right[key] for key in fixed):
            raise ValueError('Opposing-left fixed participant setup changed')
    for key in ('turning_corners', 'turning_heading_rad'):
        if first[0][key] != second[0][key]:
            raise ValueError('Opposing-left initial turning actor setup changed')
    turning = measure_opposing_left(turn)['value']
    holding = measure_opposing_left(hold)['value']
    if (turning['planned_left_cross'] != holding['planned_left_cross'] or
            turning['approach_heading_dot'] != holding['approach_heading_dot'] or
            turning['observed_turn_heading_change_rad'] ==
            holding['observed_turn_heading_change_rad']):
        raise ValueError('Opposing-left intended versus realized turn contrast missing')
    return {'format': 'worker-opposing-left-comparison-audit',
            'comparison_id': 'opposing_left_intent_vs_making',
            'turn_case': json.loads((turn / 'config.json').read_text())['selected_case_id'],
            'hold_case': json.loads((hold / 'config.json').read_text())['selected_case_id'],
            'fixed_context_sha256': digest(turn / 'opposing_left_context.json'),
            'turn_source_sha256': digest(turn / 'opposing_left_participants.jsonl'),
            'hold_source_sha256': digest(hold / 'opposing_left_participants.jsonl'),
            'turn_heading_change_rad': turning['observed_turn_heading_change_rad'],
            'hold_heading_change_rad': holding['observed_turn_heading_change_rad'],
            'legal_exception_claimed': False, 'physical_completion_claimed': False}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--turn', required=True)
    parser.add_argument('--hold', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.turn, args.hold)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
