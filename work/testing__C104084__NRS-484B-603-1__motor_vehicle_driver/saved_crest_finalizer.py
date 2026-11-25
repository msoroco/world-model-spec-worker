"""Saved-only finalization of one exact hill-crest speed-profile probe.

The three profile distinctions are construction targets, not legal thresholds.
Original source hashes, 900-frame motion and four full video decodes precede
the measurement. Physical visibility and the statutory duty remain unresolved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_crest_audit import ASSIGNMENT, PROFILES
from saved_crest_media import audit_media


def profile_witness(measurement, profile):
    if profile not in PROFILES:
        raise ValueError('unknown exact crest profile')
    start = measurement['approach_start_m']
    crest = measurement['crest_station_m']
    first = measurement.get('first_material_speed_decrease_station_m',
                            measurement['first_speed_decrease_station_m'])
    change = measurement['speed_change_mps']
    midpoint = (start + crest) / 2
    band = measurement.get('material_speed_band_mps', 0.5)
    if profile == 'early_decrease':
        matched = first is not None and start <= first < midpoint and change < -band
    elif profile == 'late_decrease':
        matched = first is not None and midpoint <= first < crest and change < -band
    else:
        matched = first is None and abs(change) <= band
    if not matched:
        raise ValueError('original approach does not realize exact crest profile')
    return {'profile': profile, 'approach_midpoint_m': midpoint,
            'first_speed_decrease_station_m': first,
            'precrest_speed_change_mps': change,
            'engineering_speed_band_mps': band,
            'basis': 'original_frame_speed_and_station',
            'legal_judgment': 'unresolved'}


def finalize(attempt, manifest, *, expected_case):
    if not isinstance(manifest, dict) or expected_case != manifest.get('case_id'):
        raise ValueError('selected exact crest case differs')
    proof = audit_media(attempt, manifest)
    profile = manifest['profile']
    if expected_case != f'{ASSIGNMENT}__{profile}':
        raise ValueError('selected exact crest profile differs')
    witness = profile_witness(proof['physical_measurements'], profile)
    return {'format': 'worker-saved-crest-finalization-v1',
            'assignment_id': ASSIGNMENT, 'case_id': expected_case,
            'source_sha256': proof['source_sha256'],
            'frame_count': proof['frame_count'],
            'crest_crossing': proof['crest_crossing'],
            'source_context': proof['source_context'],
            'speed_profile_witness': witness,
            'camera_decodes': proof['camera_decodes'],
            'checks': proof['checks'],
            'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    result = finalize(args.attempt, manifest, expected_case=args.case)
    result['source_manifest_sha256'] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    main()
