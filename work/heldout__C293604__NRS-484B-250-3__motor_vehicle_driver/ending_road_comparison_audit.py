"""Independent fixed-topology entry-order audit for the ending-road branch."""

from hashlib import sha256
import json
from pathlib import Path

from ending_road_measurement import measure


def audit(yield_case, proceed_case):
    left, right = Path(yield_case), Path(proceed_case)
    topology_name = 'intersection_topology.json'
    trace_name = 'intersection_participants.jsonl'
    for root in (left, right):
        for name in (topology_name, trace_name):
            if not (root / name).is_file():
                raise ValueError('Missing exact comparison original: ' + name)
    if sha256((left / topology_name).read_bytes()).digest() != sha256((right / topology_name).read_bytes()).digest():
        raise ValueError('Entry-order comparison changed fixed lane topology')
    first = []
    for root in (left, right):
        rows = [json.loads(line) for line in (root / trace_name).read_text().splitlines()]
        if not rows:
            raise ValueError('Entry-order comparison has no original frames')
        first.append(rows[0])
    for name in ('subject_id', 'other_id', 'subject_corners', 'other_corners'):
        if first[0].get(name) != first[1].get(name):
            raise ValueError('Entry-order comparison changed initial actor setup: ' + name)
    yielded = measure(left / topology_name, left / trace_name)
    proceeded = measure(right / topology_name, right / trace_name)
    if not yielded['subject_entered_after_other_last_conflict_frame']:
        raise ValueError('Yield case does not contain a measured delayed entry')
    if proceeded['subject_entered_after_other_last_conflict_frame']:
        raise ValueError('Proceed case did not change measured entry order')
    return {'passed': True, 'comparison_id': 'ending_through_yield_order',
            'yield_entry_delta_s': yielded['entry_delta_s'],
            'proceed_entry_delta_s': proceeded['entry_delta_s'],
            'legal_acceptance_claimed': False}
