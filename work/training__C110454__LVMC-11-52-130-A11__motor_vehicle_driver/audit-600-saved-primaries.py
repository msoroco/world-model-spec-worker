"""Independent audit of the two 30-second saved parking diagnostics."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    log = HERE / 'saved-600-primary-proof.log'
    proof = json.loads(log.read_text())
    if proof.get('format') != 'c110454-lvmc-synthetic-saved-fixture-v1':
        raise ValueError('Saved proof format differs')
    rows = proof.get('results', [])
    if {row['case_suffix'] for row in rows} != {'witness_1', 'witness_2'}:
        raise ValueError('Controlled witness pair incomplete')
    measurements = {}
    for row in rows:
        if (row['positive_exit_code'] != 0 or row['negative_exit_code'] == 0 or
                row['join_negative_exit_code'] == 0 or
                row['camera_negative_exit_code'] == 0 or
                row['frames'] != 600 or row['video_sources_decoded'] != 4 or
                row['source_unchanged'] is not True or
                row['rebuild_required'] is not True):
            raise ValueError('Saved positive or material negative incomplete')
        report = json.loads(row['positive_log'])
        if (report['original_joins']['frames'] != 600 or
                sorted(report['video_frames'].values()) != [600] * 4):
            raise ValueError('Saved frame/video coverage differs')
        value = report['measurements']['parked_body_distance_and_rest_interval']['value']
        if (value['source_frames'] != 600 or value['rest_frames'] < 40 or
                value['native_physical_observation_claimed'] is not False or
                value['legal_verdict'] is not None):
            raise ValueError('Saved parking measurement differs')
        measurements[row['case_suffix']] = value
    outside = measurements['witness_1']['nearest_parked_body_distance_m']
    inside = measurements['witness_2']['nearest_parked_body_distance_m']
    if not (outside > 4.572 > inside and
            measurements['witness_1']['sampled_relation'] == 'outside_15_ft' and
            measurements['witness_2']['sampled_relation'] == 'within_15_ft'):
        raise ValueError('Controlled parking distance contrast differs')
    result = {'format': 'c110454-600-saved-primary-audit-v1',
              'proof_log_sha256': sha(log), 'positive_cases': 2,
              'material_negative_controls': 6, 'frames_per_case': 600,
              'four_source_videos_per_case': True,
              'distance_m': {'witness_1': outside, 'witness_2': inside},
              'threshold_m': 4.572, 'source_unchanged': True,
              'synthetic_native_sample_speed': True,
              'native_physical_observation_claimed': False,
              'legal_verdict': None, 'delivery_ready': False}
    (HERE / 'saved-600-primary-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    print(json.dumps(audit()))
