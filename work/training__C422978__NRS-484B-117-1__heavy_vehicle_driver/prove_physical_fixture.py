"""CPU proof of three saved-motion outcomes using authored diagnostic rows.

The complete and incomplete source sets are reusable unit fixtures. They are
not original CARLA captures or evidence of City sidewalk designation.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'offline/reference/primary'))
from measure_saved import measure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove(case, kind):
    if kind == 'missing_evidence':
        status = 'unverified'
        sources = {'fixture_definition': sha(Path(__file__))}
        observed = {}
    else:
        suffix = 'contrast' if kind == 'complete_motion' else 'reference'
        source = HERE / f'v2-{suffix}-primary-fixture'
        metric = measure(source)
        frames = metric['moving_sidewalk_overlap_frames']
        status = 'met' if frames >= 20 else 'not_met'
        assert status == ('met' if kind == 'complete_motion' else 'not_met')
        sources = metric['source_hashes']
        observed = {'diagnostic_moving_sidewalk_overlap_frames': frames,
                    'longest_diagnostic_overlap_frames':
                    metric['longest_moving_sidewalk_overlap_frames']}
    return {'format': 'c422978-synthetic-physical-fixture-v1',
            'case_id': case, 'fixture_kind': kind,
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'original_native_observed': False, 'city_sidewalk_verified': False,
            'legal_verdict': None, 'maneuver_completed': status == 'met',
            'physical_checks': {'maneuver': {
                'status': status,
                'method': 'source-hashed 600-frame saved body and speed overlap unit fixture',
                'sources': sources, 'physical_causation_claimed': False,
                'legal_verdict_claimed': False}},
            'realized_observables': observed}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion',
                                          'missing_evidence'), required=True)
    args = parser.parse_args()
    assert args.case in {HERE.name + '__reference', HERE.name + '__contrast'}
    print(json.dumps(prove(args.case, args.kind), indent=2, sort_keys=True))
