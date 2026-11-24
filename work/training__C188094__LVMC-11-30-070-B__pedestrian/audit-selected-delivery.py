"""Independent CPU audit of one selected crossing's retained diagnostic sources."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def audit(case, attempt, saved, remove_native_source=False):
    manifest = read(HERE / 'v2-common-intersection-manifest.json')
    entries = [entry for entry in manifest['cases'] if entry['case_id'] == case]
    if len(entries) != 1:
        raise ValueError('Unknown selected exact case')
    entry = entries[0]
    number = int(case.rsplit('__probe_', 1)[1])
    recipe_name = f'v2-common{number}-fixture-recipe.json' if number < 3 else 'v2-probe3-fixture-recipe.json'
    if remove_native_source or not (attempt / 'actor-poses.jsonl').is_file():
        raise ValueError('Missing required source: actor-poses.jsonl')
    source_hashes = {}
    for item in read(HERE / recipe_name)['sources']:
        path = attempt / item['path']
        if not path.is_file() or sha(path) != item['sha256']:
            raise ValueError('Original diagnostic source differs: ' + item['path'])
        source_hashes[item['path']] = item['sha256']
    if sha(HERE / entry['construction']) != entry['construction_sha256']:
        raise ValueError('Selected construction changed')
    poses = rows(attempt / 'actor-poses.jsonl')
    frame_map = rows(attempt / 'video_frames.jsonl')
    if len(poses) != 600 or len(frame_map) != 600:
        raise ValueError('Incomplete diagnostic frame count')
    names = {'overview', 'approach', 'reference_corner', 'driver_reference'}
    for index, (pose, frame) in enumerate(zip(poses, frame_map)):
        if (pose['video_frame'] != index or frame['video_frame'] != index
                or pose['native_frame'] != frame['carla_frame']
                or set(pose['camera_native_frames']) != names
                or set(pose['camera_native_frames'].values()) != {frame['carla_frame']}):
            raise ValueError('Original frame/camera join failed')
    processing = read(saved / 'processing.json')
    result = read(saved / 'analysis/result.json')
    if (processing.get('passed') is not True or processing.get('recorded_only') is not True
            or processing.get('originals_preserved') is not True
            or processing.get('timestamp_joins', {}).get('frames') != 600
            or processing.get('analysis_revision', {}).get('construction_sha256') != entry['construction_sha256']):
        raise ValueError('Saved analysis not bound to selected exact construction')
    if result.get('accepted') is not False or result.get('legal_verdict_claimed') is not False:
        raise ValueError('Diagnostic result claims physical or legal acceptance')
    return {'format': 'c188094-selected-delivery-cpu-audit', 'passed': True,
            'case_id': case, 'construction_sha256': entry['construction_sha256'],
            'source_hashes': source_hashes, 'source_count': len(source_hashes),
            'joined_frames': len(poses), 'source_camera_names': sorted(names),
            'saved_processing_sha256': sha(saved / 'processing.json'),
            'full_video_decode_cpu_diagnostic': True,
            'actual_native_pixels_reviewed': False,
            'physical_completion_claimed': False,
            'business_district_confirmed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--saved', required=True, type=Path)
    parser.add_argument('--remove-native-source', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, args.saved, args.remove_native_source)))
