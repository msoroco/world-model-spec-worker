"""Independent fixed-condition audit for the three yield release-delay points."""

from hashlib import sha256
import json
from pathlib import Path

from ending_road_measurement import measure


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(attempts):
    if len(attempts) != 3:
        raise ValueError('Three frozen ending-road release-delay points required')
    roots = [Path(path) for path in attempts]
    configs = [json.loads((root / 'config.json').read_text()) for root in roots]
    if [config.get('release_delay_frames') for config in configs] != [0, 160, 80]:
        raise ValueError('Ending-road physical release setpoints differ')
    if any(not config['selected_case_id'].endswith(f'__yield_release_delay-{rank:04d}')
           for rank, config in enumerate(configs)):
        raise ValueError('Ending-road exact sweep case order differs')
    for name in ('intersection_topology.json', 'control_inventory.json',
                 'video_frames.jsonl', 'trace.jsonl'):
        if len({digest(root / name) for root in roots}) != 1:
            raise ValueError('Ending-road fixed original route or frame setup changed: ' + name)
    participants = [rows(root / 'intersection_participants.jsonl') for root in roots]
    if not participants[0] or len({len(x) for x in participants}) != 1:
        raise ValueError('Ending-road sweep participant histories incomplete')
    fixed = ('frame', 'time_s', 'subject_id', 'other_id', 'other_corners')
    for triplet in zip(*participants):
        if any(len({json.dumps(row[key], sort_keys=True) for row in triplet}) != 1
               for key in fixed):
            raise ValueError('Ending-road fixed through participant or frame changed')
    if any(participants[0][0]['subject_corners'] != other[0]['subject_corners']
           for other in participants[1:]):
        raise ValueError('Ending-road initial subject setup changed')
    points = []
    for root, config in zip(roots, configs):
        observed = measure(root / 'intersection_topology.json',
                           root / 'intersection_participants.jsonl')
        stream = rows(root / 'subject_displacement_m.jsonl')
        if not stream or len(stream) != len(participants[0]):
            raise ValueError('Ending-road subject displacement stream incomplete')
        entry_stream = rows(root / 'subject_entry_elapsed_s.jsonl')
        observations = observed['observations']
        if len(entry_stream) != len(observations):
            raise ValueError('Ending-road subject entry timing stream incomplete')
        latched = 0.0
        for observation, sample in zip(observations, entry_stream):
            if latched == 0.0 and observation['subject_in_conflict']:
                latched = observation['time_s']
            if sample.get('time_s') != observation['time_s'] or sample.get('value') != latched:
                raise ValueError('Ending-road subject entry timing differs from original bodies')
        points.append({'case_id': config['selected_case_id'],
                       'setpoint_frames': config['release_delay_frames'],
                       'last_displacement_m': stream[-1]['value'],
                       'entry_delta_s': observed['entry_delta_s'],
                       'subject_entry_elapsed_s': entry_stream[-1]['value'],
                       'entry_timing_stream_sha256': digest(root / 'subject_entry_elapsed_s.jsonl'),
                       'participant_source_sha256': digest(root / 'intersection_participants.jsonl'),
                       'displacement_stream_sha256': digest(root / 'subject_displacement_m.jsonl')})
    return {'format': 'worker-ending-road-physical-sweep-audit',
            'comparison_id': 'yield_release_delay_sweep',
            'fixed_topology_sha256': digest(roots[0] / 'intersection_topology.json'),
            'points': points, 'physical_realization_claimed': False,
            'legal_yield_threshold_claimed': False}


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
