"""Independent fixed-condition audit for the three physical release-delay points."""

from hashlib import sha256
import json
from pathlib import Path

from opposing_left_measurement import measure_opposing_left


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(attempts):
    if len(attempts) != 3:
        raise ValueError('Three frozen release-delay points required')
    roots = [Path(path) for path in attempts]
    configs = [json.loads((root / 'config.json').read_text()) for root in roots]
    expected = [0, 160, 80]
    if [config.get('release_delay_frames') for config in configs] != expected:
        raise ValueError('Physical release-delay setpoints differ from frozen sweep')
    cases = [config['selected_case_id'] for config in configs]
    if any(not case.endswith(f'__turn_release_delay-{i:04d}')
           for i, case in enumerate(cases)):
        raise ValueError('Exact sweep case order differs')
    for name in ('opposing_left_context.json', 'video_frames.jsonl', 'trace.jsonl'):
        if len({digest(root / name) for root in roots}) != 1:
            raise ValueError('Sweep fixed original route or frame setup changed: ' + name)
    participants = [rows(root / 'opposing_left_participants.jsonl') for root in roots]
    if not participants[0] or len({len(x) for x in participants}) != 1:
        raise ValueError('Sweep original participant histories incomplete')
    fixed = ('frame', 'time_s', 'turning_actor_id', 'opposite_actor_id',
             'opposite_corners', 'opposite_heading_rad')
    for triplet in zip(*participants):
        if any(len({json.dumps(row[key], sort_keys=True) for row in triplet}) != 1
               for key in fixed):
            raise ValueError('Sweep fixed opposite participant or frame changed')
    if any(participants[0][0][key] != other[0][key]
           for other in participants[1:] for key in ('turning_corners', 'turning_heading_rad')):
        raise ValueError('Sweep initial turning actor changed')
    values = []
    for root, source in zip(roots, participants):
        scalar = rows(root / 'turn_heading_last_rad.jsonl')
        if len(scalar) != len(source) or any(
                (row['time_s'], row['value']) !=
                (participant['time_s'], participant['turning_heading_rad'])
                for row, participant in zip(scalar, source)):
            raise ValueError('Sweep scalar heading differs from original body source')
        measured = measure_opposing_left(root)['value']
        values.append({'case_id': json.loads((root / 'config.json').read_text())['selected_case_id'],
                       'setpoint_frames': json.loads((root / 'config.json').read_text())['release_delay_frames'],
                       'last_heading_rad': scalar[-1]['value'],
                       'observed_change_rad': measured['observed_turn_heading_change_rad'],
                       'participant_source_sha256': digest(root / 'opposing_left_participants.jsonl'),
                       'heading_source_sha256': digest(root / 'turn_heading_last_rad.jsonl')})
    return {'format': 'worker-opposing-left-physical-sweep-audit',
            'comparison_id': 'turn_release_delay_sweep',
            'fixed_context_sha256': digest(roots[0] / 'opposing_left_context.json'),
            'points': values, 'legal_threshold_claimed': False,
            'physical_completion_claimed': False}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--point', action='append', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.point)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
