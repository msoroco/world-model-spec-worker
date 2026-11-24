"""Source-only bypass finalizer for a saved CPU diagnostic attempt.

The source rows used by this probe are authored requests, not CARLA observations.
This code proves joins and measurements without asserting physical or legal facts.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from prove_bypass_measurements import derive


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, relative):
    path = root / relative
    if not path.is_file():
        raise ValueError('Missing required source: ' + relative)
    return path


def decoded_frames(path):
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
         '-show_entries', 'stream=nb_read_frames',
         '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        capture_output=True, text=True, check=True, timeout=120)
    return int(result.stdout.strip())


def finalize(attempt, output):
    attempt = Path(attempt)
    output = Path(output)
    source = required(attempt, 'capture/native/pedestrian_samples.jsonl')
    context = required(attempt, 'capture/native/sidewalk_context.json')
    mapping = required(attempt, 'video_frames.jsonl')
    videos = {name: required(attempt, 'capture/cameras/' + name + '.mkv')
              for name in CAMERAS}
    originals = {str(path.relative_to(attempt)): sha(path)
                 for path in (source, context, mapping, *videos.values())}
    measurements = derive(source, context)
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    maps = [json.loads(line) for line in mapping.read_text().splitlines()]
    if len(maps) != 600:
        raise ValueError('Expected 600 video frame mappings')
    for index, (row, frame) in enumerate(zip(rows, maps)):
        if (frame.get('video_frame') != index or
                frame.get('source_frame') != row['frame'] or
                frame.get('time_s') != row['time_s'] or
                frame.get('pedestrian_xy_m') != row['pedestrian_xy_m']):
            raise ValueError('Source/video frame join differs')
    for name, path in videos.items():
        if decoded_frames(path) != 600:
            raise ValueError('Camera frame count differs: ' + name)
    if any(sha(attempt / name) != digest for name, digest in originals.items()):
        raise ValueError('Saved original source changed')
    report = {
        'format': 'c109128-saved-bypass-diagnostic-v1',
        'condition': measurements['source_sha256'],
        'measurements': measurements,
        'original_sources_sha256': originals,
        'four_camera_frames': {name: 600 for name in CAMERAS},
        'original_native_observed': False,
        'physical_obstruction_verified': False,
        'first_practicable_return_verified': False,
        'due_care_verified': False,
        'legal_verdict_claimed': False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = finalize(args.attempt, args.output)
    print(json.dumps({'frames': result['measurements']['frames'],
                      'four_camera_frames': result['four_camera_frames'],
                      'report_sha256': sha(args.output)}))
