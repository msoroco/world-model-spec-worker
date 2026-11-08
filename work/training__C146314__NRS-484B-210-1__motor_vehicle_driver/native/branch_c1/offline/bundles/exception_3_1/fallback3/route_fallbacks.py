"""Record measured paragraph (c)(1) fallback eligibility without selecting a case."""
import argparse
import json
from pathlib import Path

from saved import measure


def route(bundle, saved):
    measured = measure(bundle, saved)
    spans = measured['spans']
    relation = spans[0]['boundary_relation'] if len(spans) == 1 else 'missing_or_multiple_spans'
    missing_pass = measured['right_pass_frames'] < 1
    distance_uncertain = relation in ('ambiguous', 'incomplete_exit', 'missing_or_multiple_spans')
    review_missing = measured['reviewed_boundary_pavement_frames'] < 240
    original_missing = not measured['original_native_observed']
    return {'format': 'c146314-paragraph-c1-measured-routing-v1',
            'case_id': measured['case_id'],
            'candidate_id': measured['candidate_id'],
            'source_kind': measured['source_kind'],
            'measured_boundary_relation': relation,
            'triggers': {
                'fallback1': {'eligible': missing_pass or distance_uncertain,
                              'measured_right_pass_frames': measured['right_pass_frames'],
                              'boundary_relation': relation,
                              'reason': 'insufficient full-body pass or uncertain sampled distance'},
                'fallback2': {'eligible': review_missing,
                              'measured_reviewed_boundary_pavement_frames':
                                  measured['reviewed_boundary_pavement_frames'],
                              'reason': 'fewer than 240 reviewed boundary/pavement frames'},
                'fallback3': {'eligible': original_missing or relation == 'incomplete_exit',
                              'original_native_observed': measured['original_native_observed'],
                              'exit_observed': len(spans) == 1 and spans[0]['exit_observed'],
                              'reason': 'missing original Native evidence or incomplete exit'}},
            'selected_fallback': None, 'delivery_ready': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--saved', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(route(a.bundle, a.saved)))
