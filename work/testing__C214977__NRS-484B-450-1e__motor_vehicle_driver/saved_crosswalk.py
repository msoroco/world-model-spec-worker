"""Independent saved-source verification before pinned media and delivery audits."""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import json
from PIL import Image

from crosswalk import footprint_relation, measure, require, sealed_json
from native_capture import CAMERAS, CAMERA_SIZES


def comparison_source(receipt_ref: dict, source_root: Path, attempt_root: Path,
                      expected_case: dict, verified: dict) -> dict:
    """Prepare a sealed candidate source for later independent delivery review.

    This records original source facts only. It cannot set delivery_accepted or
    physical_completion; those require the local delivery auditor.
    """
    require(verified['source_verified'] is True and verified['case_id'] == expected_case['case_id']
            and verified['decoded_original_pngs'] == 3600, 'saved source verification required')
    receipt = sealed_json(receipt_ref, attempt_root)
    site = sealed_json(receipt['site_source'], source_root)
    vehicle = sealed_json(receipt['vehicle_source'], source_root)
    rows = sealed_json(receipt['sources']['actor_rows'], attempt_root)
    flags = {'traffic_conflict': 'traffic_conflict', 'law': 'law_direction',
             'police_direction': 'police_direction', 'device_direction': 'device_direction'}
    active = [r for r in rows if r['halt_activity'] == expected_case['action'] and r['speed_mps'] < 0.1]
    require(active, 'no measured halt activity')
    overlap = [footprint_relation(r['body_corners_xy'], site['crosswalk_polygon'])['overlap'] for r in active]
    require(all(overlap) or not any(overlap), 'mixed crosswalk placement during halt')
    observed_destination = 'on' if all(overlap) else 'off'
    require(observed_destination == expected_case['destination'], 'measured destination mismatch')
    camera_profile = {name: CAMERA_SIZES[name] for name in CAMERAS}
    camera_hash = hashlib.sha256(json.dumps(camera_profile, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'format': 'crosswalk-comparison-source', 'case_id': expected_case['case_id'],
            'law_id': 'NRS-484B-450-1e', 'actor': 'motor_vehicle_driver',
            'cell_id': site['cell_id'], 'map_name': site['map_name'],
            'crosswalk_id': site['crosswalk_id'], 'site_source_sha256': receipt['site_source']['sha256'],
            'crosswalk_polygon': site['crosswalk_polygon'], 'parking_route': site['parking_route'],
            'vehicle_source_sha256': receipt['vehicle_source']['sha256'],
            'vehicle_blueprint': vehicle['blueprint'], 'camera_plan_sha256': camera_hash,
            'original_frame_count': receipt['frame_count'], 'source_format': receipt['source_format'],
            'action': expected_case['action'], 'destination': observed_destination,
            'exception': expected_case['exception'],
            'exception_sources': {name: any(r[key] for r in active) for name, key in flags.items()},
            'source_receipt_sha256': receipt_ref['sha256'],
            'physical_completion': False, 'delivery_accepted': False}


def verify(receipt_ref: dict, source_root: Path, attempt_root: Path, expected_case: dict) -> dict:
    receipt = sealed_json(receipt_ref, attempt_root)
    require(receipt['format'] == 'crosswalk-native-source-receipt', 'Native receipt format mismatch')
    require(receipt['case_id'] == expected_case['case_id'], 'Native case mismatch')
    require(receipt['source_format'] == 'native_original' and receipt['fps'] == 20 and receipt['frame_count'] == 900,
            'Native profile mismatch')
    require(receipt.get('camera_source_format') == 'png_original', 'original camera pixel source missing')
    site = sealed_json(receipt['site_source'], source_root)
    sealed_json(receipt['vehicle_source'], source_root)
    rows = sealed_json(receipt['sources']['actor_rows'], attempt_root)
    mapping = sealed_json(receipt['sources']['frame_map'], attempt_root)
    cameras = sealed_json(receipt['sources']['camera_readbacks'], attempt_root)
    require(len(rows) == len(mapping) == 900, 'original frame source incomplete')
    require(set(cameras) == set(CAMERAS) and all(len(cameras[name]) == 900 for name in CAMERAS),
            'original camera readbacks incomplete')
    decoded = 0
    for i, row in enumerate(rows):
        require(mapping[i] == {'frame': row['frame'], 'time_s': row['time_s']}, 'original frame map mismatch')
        require(all(cameras[name][i]['frame'] == row['frame'] and cameras[name][i]['source_id'] for name in CAMERAS),
                'original camera frame join mismatch')
        for name in CAMERAS:
            ref = cameras[name][i]
            path = (attempt_root.resolve() / ref['path']).resolve()
            require(path.is_relative_to(attempt_root.resolve()), 'camera source escapes attempt')
            require(path.suffix == '.png' and path.is_file(), 'original camera PNG absent')
            require(hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256'], 'camera PNG hash mismatch')
            with Image.open(path) as source:
                require(source.format == 'PNG' and source.size == CAMERA_SIZES[name], 'camera PNG profile mismatch')
                source.load()
            decoded += 1
    expected = {'case_id': expected_case['case_id'], 'subject_id': receipt['subject_id'],
                'first_frame': rows[0]['frame'], 'frame_count': 900,
                'crosswalk_id': site['crosswalk_id'], 'marking_status': site['marking_status'],
                'crosswalk_polygon': site['crosswalk_polygon'], 'action': expected_case['action'],
                'exception': expected_case['exception']}
    observed = measure(rows, expected)
    require(observed == receipt['measurement'], 'Native measurement drift')
    return {'format': 'crosswalk-saved-source-verification', 'case_id': expected_case['case_id'],
            'source_verified': True, 'original_frames': 900, 'camera_readbacks': list(CAMERAS),
            'decoded_original_pngs': decoded, 'measurement': observed,
            'full_video_decode': False, 'actual_pixels': True,
            'physical_completion': False, 'legal_judgment': 'unresolved'}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--attempt-root', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--case', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--comparison-source-output', type=Path)
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
    if args.comparison_source_output:
        source = comparison_source(receipt_ref, args.source_root, attempt_root, case, result)
        args.comparison_source_output.write_text(json.dumps(source, indent=2) + '\n')


if __name__ == '__main__':
    main()
