"""Saved-only source review for a C179480 Native capture.

This reports measured motion and source integrity. It never supplies a Native
result, physical acceptance, or a legal conclusion.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from source_measurement import analyze, analyze_hazard


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def video_frames(path):
    process = subprocess.run(
        ['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
         '-show_entries', 'stream=nb_read_frames',
         '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        capture_output=True, text=True, timeout=120, check=False)
    if process.returncode or not process.stdout.strip().isdigit():
        raise ValueError('Source video decode failed: ' + str(path))
    return int(process.stdout.strip())


def review(attempt, output, *, write=True):
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    if output.exists() or output.parent != attempt:
        raise ValueError('Saved review needs a new output inside the original attempt')
    actor = attempt / 'native-actors.jsonl'
    mapping = attempt / 'video_frames.jsonl'
    measured = analyze(actor, mapping)
    count = measured['sample_count']
    sources = {'native-actors.jsonl': sha256(actor),
               'video_frames.jsonl': sha256(mapping)}
    map_path = attempt / 'native-map-readback.json'
    measurement_path = attempt / 'source-measurements.json'
    map_readback = json.loads(map_path.read_text())
    receipt = json.loads(measurement_path.read_text())
    if map_readback.get('case') == 'safe_operation_stop':
        observed_hazard = analyze_hazard(actor, mapping)
        if receipt.get('hazard_observation') != observed_hazard:
            raise ValueError('Saved hazard receipt differs from original sources')
    if (map_readback.get('format') != 'c179480-original-map-readback-v1'
            or receipt.get('format') != 'c179480-source-measurements-v1'
            or receipt.get('actor_source_sha256') != sources['native-actors.jsonl']
            or receipt.get('frame_map_sha256') != sources['video_frames.jsonl']
            or receipt.get('map_readback_sha256') != sha256(map_path)
            or any(receipt.get(key) != value for key, value in measured.items())):
        raise ValueError('Saved map/measurement receipt differs from original sources')
    sources['native-map-readback.json'] = sha256(map_path)
    sources['source-measurements.json'] = sha256(measurement_path)
    counts = {}
    for name in CAMERAS:
        relative = name + '.mkv'
        video = attempt / relative
        if not video.is_file():
            raise ValueError('Missing original source camera: ' + relative)
        counts[name] = video_frames(video)
        if counts[name] != count:
            raise ValueError('Original source camera count differs: ' + relative)
        sources[relative] = sha256(video)
    report = {
        'format': 'c179480-saved-source-review-v1',
        'source_frames': count,
        'camera_frames': counts,
        'source_sha256': sources,
        'measured_values': measured,
        'physical_completion_claimed': False,
        'legal_verdict_claimed': False,
        'independent_review_required': [
            'normal and reasonable traffic impediment or blockage',
            'safe operation necessity', 'compliance with law',
            'roadway and camera visibility'],
    }
    if write:
        with output.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write('\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('attempt', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    review(args.attempt, args.output)


if __name__ == '__main__':
    main()
