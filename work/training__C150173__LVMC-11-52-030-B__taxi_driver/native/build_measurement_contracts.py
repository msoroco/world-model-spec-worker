"""Bind every selected passenger and freight case to exact saved inputs."""
import json
from pathlib import Path

from freight_finalize import SOURCES as FREIGHT_SOURCES
from freight_plan import PURPOSES


PACKAGE = Path(__file__).resolve().parent.parent
PASSENGER_INPUTS = ['yellow-zone-native.jsonl', 'sign-review.json',
                    'commercial-status-review.json', 'passenger-purpose-review.json',
                    'ordinary-rules-review.json', 'observed-passenger-activity.jsonl']


def main():
    for entry in json.loads((PACKAGE / 'selected-draft-manifest.json').read_text())['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[1]
        freight = suffix in PURPOSES
        sources = [name for name in FREIGHT_SOURCES if name != 'yellow-freight-road.xodr'] if freight else PASSENGER_INPUTS
        negative = 'freight-purpose-review.json' if freight else 'observed-passenger-activity.jsonl'
        contract = {
            'format': 'worker-measurement-contract', 'case_id': case,
            'requirements': [{
                'disposition_index': 1 if freight else 0,
                'requirement': 'Commercial vehicle freight-loading alternative' if freight
                               else 'LVMC-11-52-030-B',
                'source': 'LVMC 11.52.030(B)(1)' if freight else 'LVMC 11.52.030(B)',
                'output_key': 'freight_yellow_zone_measurement' if freight
                              else 'taxi_yellow_zone_measurement',
                'method': 'source_measurement' if freight else 'source_join_measurement',
                'kind': 'measured', 'value_type': 'object', 'inputs': sources}],
            'negative': {'remove': [negative],
                         'error_contains': 'Missing required source: ' + negative},
            'frame_count': 600, 'sampling_rate_hz': 20, 'duration_s': 30,
            'physical_acceptance_claimed': False,
            'source_required': (
                ['original Native taxi and cargo actor identity/body traces',
                 'original taxi commercial-use classification source',
                 'authoritative freight sign and cargo-purpose review'] if freight else
                ['original Native taxi body and velocity',
                 '600 aligned original frames from four cameras',
                 'source-based taxicab identity review',
                 'actor-bound original commercial-use classification source',
                 'source-based yellow curb and posted sign review',
                 'source-based passenger-purpose and ordinary-rule review']),
            'measured_channels': (
                ['cargo_displacement_m', 'cargo_transfer_motion_frames', 'observed_purpose'] if freight else
                ['stopped_frames', 'yellow_zone_body_frames', 'posted_active_stopped_frames', 'observed_purpose']),
            'source_finalizer': 'native/freight_finalize.py' if freight else 'native/finalize_original.py',
            'review_sealer': 'native/freight_seal_review.py' if freight else 'native/seal_review.py',
            'original_native_observed': False, 'legal_verdict': None}
        path = PACKAGE / 'native-selected' / suffix / 'measurement-contract.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(contract, indent=2) + '\n')
    print('seven exact measurement contracts')


if __name__ == '__main__':
    main()
