"""Independent checks for the small first-case source-shaped CPU diagnostic."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(root, negative):
    from worker_exchange.media import audit

    root, negative = Path(root), Path(negative)
    result = json.loads((root / 'result.json').read_text())
    report = json.loads((root.parent / 'c125697-primary-entry-analysis.json').read_text())
    if result['case_id'] != report['case_id'] or result['physical_checks']['maneuver']['status'] not in ('met', 'not_met', 'unverified'):
        raise ValueError('Diagnostic result differs from saved analysis')
    if report['physical_acceptance_claimed'] is not False:
        raise ValueError('Diagnostic claims physical acceptance')
    if result['measured_values']['other_spatially_right_of_ego_approach'] is not True:
        raise ValueError('Diagnostic right-side geometry missing')
    if abs(result['measured_values']['absolute_entry_time_difference_s'] - .05) > 1e-9:
        raise ValueError('Diagnostic entry timing differs')
    frames = [json.loads(row) for row in (root / 'video_frames.jsonl').read_text().splitlines()]
    if len(frames) != 3:
        raise ValueError('Expected three diagnostic source frames')
    frame_sha = sha(root / 'video_frames.jsonl')
    cameras = {}
    for name, dimensions in {'overview': [1920, 1080], 'approach': [1280, 720],
                             'reference_corner': [1280, 720],
                             'driver_reference': [1280, 720]}.items():
        receipt = audit(root / (name + '.mkv'), 3, mapping_sha256=frame_sha)
        if receipt['passed'] is not True or receipt['dimensions'] != dimensions:
            raise ValueError('Source camera decode failed: ' + name)
        cameras[name] = {'frames': receipt['frames'],
                         'dimensions': receipt['dimensions'],
                         'sha256': receipt['video_sha256']}
    if (negative / 'overview.mkv').exists() or (negative / 'result.json').exists():
        raise ValueError('Negative diagnostic acquired result or missing camera')
    return {'format': 'c125697-source-shaped-diagnostic-check',
            'positive_result_sha256': sha(root / 'result.json'),
            'source_frame_map_sha256': frame_sha,
            'negative_missing_camera': True,
            'source_cameras': cameras,
            'physical_acceptance_claimed': False,
            'complete_saved_processing_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--negative', required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.root, args.negative), indent=2))


if __name__ == '__main__':
    main()
