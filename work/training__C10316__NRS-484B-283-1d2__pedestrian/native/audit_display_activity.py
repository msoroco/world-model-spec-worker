"""Diagnostic display-pixel activity check; not a legibility or governance audit.

The region of interest must be chosen from original camera geometry. A passing
result only shows that those decoded pixels respond to the retained illumination
schedule. It cannot identify a pedestrian signal or read its digits.
"""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess


def sha_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def audit(attempt, roi, minimum_contrast=15.0):
    attempt = Path(attempt)
    samples_path = attempt / 'countdown_samples.jsonl'
    video = attempt / 'display_close.mkv'
    if not samples_path.is_file() or not video.is_file():
        raise ValueError('Missing display activity source')
    samples = [json.loads(line) for line in samples_path.read_text().splitlines() if line.strip()]
    if len(samples) < 600:
        raise ValueError('Display activity needs a full 30-second source')
    if len(roi) != 4 or any(type(value) is not int for value in roi):
        raise ValueError('Invalid display ROI')
    x, y, width, height = roi
    if x < 0 or y < 0 or width < 8 or height < 8:
        raise ValueError('Invalid display ROI')
    filter_spec = f'crop={width}:{height}:{x}:{y},scale=32:32'
    command = ['ffmpeg', '-nostdin', '-v', 'error', '-i', str(video),
               '-vf', filter_spec, '-f', 'rawvideo', '-pix_fmt', 'gray', '-']
    decoded = subprocess.run(command, capture_output=True, timeout=300)
    if decoded.returncode:
        raise ValueError('Display activity decode failed')
    frame_bytes = 32 * 32
    if len(decoded.stdout) != len(samples) * frame_bytes:
        raise ValueError('Display activity decoded frame count differs')
    means = [sum(decoded.stdout[index*frame_bytes:(index+1)*frame_bytes]) / frame_bytes
             for index in range(len(samples))]
    lit, unlit = [], []
    for index, (sample, mean) in enumerate(zip(samples, means)):
        if sample.get('native_frame') != samples[0].get('native_frame') + index:
            raise ValueError('Display activity Native frame sequence differs')
        illuminated = sample.get('display_illuminated')
        if type(illuminated) is not bool:
            raise ValueError('Display activity schedule missing')
        if sample.get('indication') == 'dont_walk_flashing':
            (lit if illuminated else unlit).append(mean)
    if len(lit) < 20 or len(unlit) < 20:
        raise ValueError('Display activity lacks flashing phases')
    delta = statistics.median(lit) - statistics.median(unlit)
    if delta < minimum_contrast:
        raise ValueError('Display pixels do not follow illumination schedule')
    return {'format': 'c10316-display-activity-diagnostic-v1',
            'frames': len(samples), 'roi_xywh': list(roi),
            'median_lit_minus_unlit': round(delta, 3),
            'minimum_contrast': minimum_contrast,
            'video_sha256': sha_file(video),
            'samples_sha256': sha_file(samples_path),
            'pixel_activity_verified': True, 'digit_legibility_verified': False,
            'signal_governance_verified': False, 'physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--roi', nargs=4, type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.roi), sort_keys=True))
