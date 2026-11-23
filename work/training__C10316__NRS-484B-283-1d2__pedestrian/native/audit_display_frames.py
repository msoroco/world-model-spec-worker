"""Independently bind saved display video pixels to original Native RGB hashes.

This checks pixel integrity and frame joins only. It cannot establish that the
pixels show a legible governing pedestrian signal.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    if not path.is_file():
        raise ValueError('Missing display source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def dimensions(video):
    result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height', '-of', 'json', str(video)],
        capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError('Display video probe failed')
    streams = json.loads(result.stdout).get('streams', [])
    if len(streams) != 1:
        raise ValueError('Display video stream missing or ambiguous')
    width, height = streams[0].get('width'), streams[0].get('height')
    if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
        raise ValueError('Display video dimensions invalid')
    return width, height


def read_exact(stream, count):
    parts = []
    remaining = count
    while remaining:
        part = stream.read(remaining)
        if not part:
            break
        parts.append(part)
        remaining -= len(part)
    return b''.join(parts)


def audit(attempt, expected_frames):
    attempt = Path(attempt)
    if type(expected_frames) is not int or expected_frames < 240:
        raise ValueError('Display audit needs a full declared frame window')
    video = attempt / 'display_close.mkv'
    if not video.is_file():
        raise ValueError('Missing display source: display_close.mkv')
    samples_path = attempt / 'countdown_samples.jsonl'
    map_path = attempt / 'video_frames.jsonl'
    samples, mapping = rows(samples_path), rows(map_path)
    if len(samples) != expected_frames or len(mapping) != expected_frames:
        raise ValueError('Display source frame count differs')
    first_time = samples[0].get('time_s')
    if type(first_time) not in (int, float) or not math.isfinite(first_time):
        raise ValueError('Display source time missing')
    for index, (sample, joined) in enumerate(zip(samples, mapping)):
        frame = sample.get('native_frame')
        expected_time = first_time + index / 20
        if (type(frame) is not int or joined.get('native_frame') != frame or
                joined.get('carla_frame') != frame or joined.get('video_frame') != index or
                (index and frame <= samples[index - 1]['native_frame'])):
            raise ValueError('Display Native/video frame join differs at ' + str(index))
        if any(type(value) not in (int, float) or not math.isfinite(value) or
               abs(value - expected_time) > .002 for value in
               (sample.get('time_s'), joined.get('time_s'))):
            raise ValueError('Display Native/video time join differs at ' + str(index))
        a = sample.get('original_display_frame_sha256')
        b = joined.get('source_rgb_sha256', {}).get('display_close')
        if not isinstance(a, str) or len(a) != 64 or a != b:
            raise ValueError('Original display RGB hash join differs at ' + str(index))
    width, height = dimensions(video)
    frame_bytes = width * height * 3
    command = ['ffmpeg', '-nostdin', '-v', 'error', '-i', str(video),
               '-map', '0:v:0', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for index, sample in enumerate(samples):
            pixels = read_exact(process.stdout, frame_bytes)
            if len(pixels) != frame_bytes:
                raise ValueError('Decoded display frame count differs')
            if hashlib.sha256(pixels).hexdigest() != sample['original_display_frame_sha256']:
                raise ValueError('Decoded display pixels differ at ' + str(index))
        if process.stdout.read(1):
            raise ValueError('Decoded display has extra frames')
        stderr = process.stderr.read()
        if process.wait(timeout=30) != 0:
            raise ValueError('Display video decode failed: ' + stderr.decode(errors='replace')[:200])
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
        process.stderr.close()
    return {'format': 'c10316-display-rgb-source-audit-v1',
            'frames': expected_frames, 'rate_hz': 20, 'width': width, 'height': height,
            'video_sha256': sha(video), 'samples_sha256': sha(samples_path),
            'frame_map_sha256': sha(map_path), 'pixel_integrity_verified': True,
            'signal_legibility_verified': False, 'signal_governance_verified': False,
            'physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--frames', type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.frames), sort_keys=True))
