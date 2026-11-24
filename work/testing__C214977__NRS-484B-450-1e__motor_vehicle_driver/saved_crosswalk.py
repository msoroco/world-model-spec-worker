"""Independent saved-source verification before pinned media and delivery audits."""
from __future__ import annotations

from pathlib import Path
import argparse
import json

from crosswalk import measure, require, sealed_json
from native_capture import CAMERAS


def verify(receipt_ref: dict, source_root: Path, attempt_root: Path, expected_case: dict) -> dict:
    receipt = sealed_json(receipt_ref, attempt_root)
    require(receipt['format'] == 'crosswalk-native-source-receipt', 'Native receipt format mismatch')
    require(receipt['case_id'] == expected_case['case_id'], 'Native case mismatch')
    require(receipt['source_format'] == 'native_original' and receipt['fps'] == 20 and receipt['frame_count'] == 900,
            'Native profile mismatch')
    site = sealed_json(receipt['site_source'], source_root)
    sealed_json(receipt['vehicle_source'], source_root)
    rows = sealed_json(receipt['sources']['actor_rows'], attempt_root)
    mapping = sealed_json(receipt['sources']['frame_map'], attempt_root)
    cameras = sealed_json(receipt['sources']['camera_readbacks'], attempt_root)
    require(len(rows) == len(mapping) == 900, 'original frame source incomplete')
    require(set(cameras) == set(CAMERAS) and all(len(cameras[name]) == 900 for name in CAMERAS),
            'original camera readbacks incomplete')
    for i, row in enumerate(rows):
        require(mapping[i] == {'frame': row['frame'], 'time_s': row['time_s']}, 'original frame map mismatch')
        require(all(cameras[name][i]['frame'] == row['frame'] and cameras[name][i]['source_id'] for name in CAMERAS),
                'original camera frame join mismatch')
    expected = {'case_id': expected_case['case_id'], 'subject_id': receipt['subject_id'],
                'first_frame': rows[0]['frame'], 'frame_count': 900,
                'crosswalk_id': site['crosswalk_id'], 'marking_status': site['marking_status'],
                'crosswalk_polygon': site['crosswalk_polygon'], 'action': expected_case['action'],
                'exception': expected_case['exception']}
    observed = measure(rows, expected)
    require(observed == receipt['measurement'], 'Native measurement drift')
    return {'format': 'crosswalk-saved-source-verification', 'case_id': expected_case['case_id'],
            'source_verified': True, 'original_frames': 900, 'camera_readbacks': list(CAMERAS),
            'measurement': observed, 'full_video_decode': False, 'actual_pixels': False,
            'physical_completion': False, 'legal_judgment': 'unresolved'}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--attempt-root', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--case', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    receipt_path = args.receipt.resolve()
    attempt_root = args.attempt_root.resolve()
    require(receipt_path.is_relative_to(attempt_root), 'Native receipt outside attempt')
    import hashlib
    receipt_ref = {'path': str(receipt_path.relative_to(attempt_root)),
                   'sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest()}
    case = json.loads(args.case.read_text())
    result = verify(receipt_ref, args.source_root, attempt_root, case)
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
