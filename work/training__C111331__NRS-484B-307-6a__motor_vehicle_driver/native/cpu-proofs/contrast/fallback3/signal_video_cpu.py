"""Decode synthetic signal-head pixels and join them to saved Native phases.

This strict color classifier is a CPU fixture diagnostic. Original CARLA frames
need their own calibrated signal crop and independent reviewer before selection.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

WIDTH = 16
HEIGHT = 16
FRAME_BYTES = WIDTH * HEIGHT * 3
COLORS = {'green': (0, 255, 0), 'yellow': (255, 255, 0), 'red': (255, 0, 0)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def inspect(source_dir, video_path, ffmpeg):
    source_dir = Path(source_dir)
    video_path = Path(video_path)
    native = rows(source_dir / 'native_samples.jsonl')
    mapping = rows(source_dir / 'video_frames.jsonl')
    if len(native) != 480 or len(mapping) != 480:
        raise ValueError('Saved signal video requires 480 source rows')
    command = [str(ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'error',
               '-i', str(video_path), '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1']
    decoded = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if decoded.returncode:
        raise ValueError('Lossless signal video decode failed: ' + decoded.stderr.decode(errors='replace')[-250:])
    if len(decoded.stdout) != FRAME_BYTES * 480:
        raise ValueError('Decoded signal video frame count or dimensions differ')
    frame_hashes = []
    phases = []
    for i, (sample, join) in enumerate(zip(native, mapping)):
        if (join['video_frame'] != i or join['native_frame'] != sample['native_frame'] or
                join['carla_frame'] != sample['native_frame']):
            raise ValueError('Saved signal video Native frame join differs')
        frame = decoded.stdout[i * FRAME_BYTES:(i + 1) * FRAME_BYTES]
        frame_hashes.append(hashlib.sha256(frame).hexdigest())
        pixels = [frame[j:j+3] for j in range(0, len(frame), 3)]
        mean = tuple(sum(pixel[c] for pixel in pixels) // len(pixels) for c in range(3))
        phase = min(COLORS, key=lambda p: sum(abs(mean[c] - COLORS[p][c]) for c in range(3)))
        if sum(abs(mean[c] - COLORS[phase][c]) for c in range(3)) > 20:
            raise ValueError('Decoded synthetic signal color is ambiguous')
        expected = sample['observed_signal_state'].lower().rsplit('.', 1)[-1]
        if phase != expected:
            raise ValueError('Decoded signal color disagrees with saved Native phase')
        phases.append(phase)
    return {'format': 'c111331-synthetic-signal-video-cpu-v1',
            'source_kind': 'synthetic_cpu_color_fixture',
            'video_sha256': sha(video_path),
            'native_samples_sha256': sha(source_dir / 'native_samples.jsonl'),
            'video_frames_sha256': sha(source_dir / 'video_frames.jsonl'),
            'decoded_frame_sha256': frame_hashes,
            'phase_counts': {p: phases.count(p) for p in COLORS},
            'decoded_frames': len(phases), 'original_carla_pixels_verified': False,
            'physical_signal_state_verified': False}


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--source-dir', required=True)
    p.add_argument('--video', required=True)
    p.add_argument('--ffmpeg', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    result = inspect(a.source_dir, a.video, a.ffmpeg)
    Path(a.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'decoded_frame_sha256'}, sort_keys=True))
