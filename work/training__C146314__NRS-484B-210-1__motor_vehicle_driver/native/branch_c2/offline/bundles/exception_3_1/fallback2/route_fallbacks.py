"""Record measured private-way fallback eligibility without selecting a case."""
import argparse
import json
from pathlib import Path
from saved import measure


def route(bundle, saved):
    m = measure(bundle, saved)
    spans = m['spans']
    crossing_complete = len(spans) == 1 and spans[0]['exit_observed'] and m['body_crossed_spur_plane']
    return {'format': 'c146314-paragraph-c2-measured-routing-v1',
            'case_id': m['case_id'], 'candidate_id': m['candidate_id'],
            'source_kind': m['source_kind'],
            'triggers': {
                'fallback1': {'eligible': m['right_pass_frames'] < 1 or
                              (m['private_way_requested'] and not crossing_complete),
                              'measured_right_pass_frames': m['right_pass_frames'],
                              'body_crossed_spur_plane': m['body_crossed_spur_plane'],
                              'reason': 'insufficient full-body pass or incomplete spur crossing'},
                'fallback2': {'eligible': m['reviewed_private_way_pavement_frames'] < 240,
                              'measured_reviewed_private_way_pavement_frames':
                                  m['reviewed_private_way_pavement_frames'],
                              'reason': 'fewer than 240 private-way/pavement reviewed frames'},
                'fallback3': {'eligible': not m['original_native_observed'] or
                              (m['private_way_requested'] and not crossing_complete),
                              'original_native_observed': m['original_native_observed'],
                              'reason': 'missing original Native evidence or incomplete crossing'}},
            'selected_fallback': None, 'delivery_ready': False}


if __name__ == '__main__':
    q = argparse.ArgumentParser()
    q.add_argument('--bundle', type=Path, required=True)
    q.add_argument('--saved', type=Path, required=True)
    a = q.parse_args()
    print(json.dumps(route(a.bundle, a.saved)))
