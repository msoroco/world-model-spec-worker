"""Exercise one exact selected delivery audit without claiming Native acceptance."""
import argparse
import json
from pathlib import Path

from audit_selected_delivery import PACKAGE, audit, read


def check(case_id, corrupt_final_join=False):
    manifest = read(PACKAGE / 'execution-manifest.json')
    cases = [case for case in manifest['cases'] if case['case_id'] == case_id]
    if len(cases) != 1:
        raise ValueError('Select one exact delivery case')
    case = cases[0]
    records = [audit(case, candidate, corrupt_final_join=corrupt_final_join)
               for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')]
    if any(record['case_id'] != case_id or
           record['frames_joined'] != 600 or
           len(record['videos_fully_decoded']) != 5 or
           record['source_kind'] != 'synthetic_native_sample' or
           record['accepted'] is not False or
           record['original_native_verified'] is not False or
           record['actual_pixels_verified'] is not False or
           record['physical_completion_verified'] is not False
           for record in records):
        raise ValueError('Source delivery diagnostic changed')
    return {'case_id': case_id, 'candidate_count': len(records),
            'source_join_frames': 600, 'source_videos_decoded_per_candidate': 5,
            'checks_exercised': ['native_source', 'all_participants', 'time_join',
                                 'full_video_decode', 'actual_pixels',
                                 'physical_completion'],
            'source_kind': 'synthetic_native_sample', 'diagnostic_only': True,
            'accepted': False, 'original_native_verified': False,
            'actual_pixels_verified': False,
            'physical_completion_verified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--corrupt-final-join', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.case, args.corrupt_final_join)))
