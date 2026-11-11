"""Independent original-source audit of the authored arrival-timing contrast."""

from hashlib import sha256
import json
from pathlib import Path

from ending_road_measurement import measure


def audit(near_case, separated_case):
    roots = [Path(near_case), Path(separated_case)]
    for root in roots:
        for name in ('intersection_topology.json', 'intersection_participants.jsonl'):
            if not (root / name).is_file():
                raise ValueError('Missing exact arrival original: ' + name)
    topology = [(root / 'intersection_topology.json').read_bytes() for root in roots]
    if sha256(topology[0]).digest() != sha256(topology[1]).digest():
        raise ValueError('Arrival comparison changed fixed lane topology')
    starts = [json.loads((root / 'intersection_participants.jsonl').read_text().splitlines()[0])
              for root in roots]
    for name in ('subject_id', 'other_id', 'subject_corners', 'other_corners'):
        if starts[0].get(name) != starts[1].get(name):
            raise ValueError('Arrival comparison changed initial actor setup: ' + name)
    observations = [measure(root / 'intersection_topology.json',
                            root / 'intersection_participants.jsonl') for root in roots]
    if not all(row['subject_entered_after_other_last_conflict_frame'] for row in observations):
        raise ValueError('Arrival comparison changed yielding order')
    if observations[1]['entry_delta_s'] <= observations[0]['entry_delta_s']:
        raise ValueError('Separated arrival lacks a measured later entry')
    return {'passed': True, 'comparison_id': 'arrival_timing_applicability',
            'near_entry_delta_s': observations[0]['entry_delta_s'],
            'separated_entry_delta_s': observations[1]['entry_delta_s'],
            'legal_approximately_same_time_judgment': None}
