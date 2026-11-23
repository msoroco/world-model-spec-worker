"""Retain and compare exact 600-frame synthetic sources for the selected intent.

This is a CPU source-processing proof, not an original Native or legal finding.
"""
import hashlib
import json
from pathlib import Path

from prove_saved import fixture
from saved import process

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ASSIGNMENT = 'training__C109137__NRS-484B-217-2__motor_vehicle_driver'
OUT = ROOT / '.runtime-work' / 'c109137-current-pair-sources'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    records = []
    for suffix in ('probe_1', 'probe_2'):
        bundle = HERE / 'drafts' / suffix / 'primary'
        folder = OUT / suffix
        raw, video, review = fixture(bundle, folder)
        measurement = process(bundle, raw, video, review, synthetic=True)
        records.append({
            'case_id': ASSIGNMENT + '__' + suffix,
            'candidate_id': 'primary',
            'bundle_config_sha256': digest(bundle / 'config.json'),
            'requested_tracks_sha256': digest(bundle / 'requested-tracks.jsonl'),
            'sources': {p.name: digest(p) for p in (raw, video, review)},
            'measurement': measurement,
        })
    left, right = (row['measurement'] for row in records)
    fixed = ('frames', 'observed_stripe_body_frames',
             'first_observed_stripe_frame', 'first_adjoining_lane_frame',
             'stripe_review_fraction', 'minimum_other_traffic_speed_mps')
    if any(left[key] != right[key] for key in fixed):
        raise AssertionError('Controlled crossing geometry or traffic changed')
    if left['first_observed_signal_frame'] is None or right['first_observed_signal_frame'] is not None:
        raise AssertionError('Signal intervention missing')
    if not (left['observed_signal_lead_s'] > 0 and right['observed_signal_lead_s'] is None):
        raise AssertionError('Prior-signal comparison failed')
    if not (left['first_adjoining_lane_frame'] is not None and
            left['first_adjoining_lane_frame'] == right['first_adjoining_lane_frame']):
        raise AssertionError('Adjoining-road request did not persist')
    if any(row['measurement']['delivery_ready'] for row in records):
        raise AssertionError('Synthetic source claimed physical acceptance')
    receipt = {
        'format': 'c109137-current-600-frame-synthetic-pair-v1',
        'source_kind': 'synthetic_fixture', 'rate_hz': 20, 'frames': 600,
        'controlled_variable': 'observed_left_indicator',
        'fixed_measurements': list(fixed), 'records': records,
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
        'passed': True,
    }
    path = HERE / 'current-pair-source-proof.json'
    path.write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'passed': True, 'receipt_sha256': digest(path),
                      'signal_lead_s': left['observed_signal_lead_s'],
                      'crossing_frame': left['first_observed_stripe_frame']}))


if __name__ == '__main__':
    main()
