"""Independent decoded-video audit for eight synthetic signal CPU fixtures."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FFMPEG = REPO / '.runtime-work/linux_arm64/ffmpeg'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit():
    summary = json.loads((HERE / 'signal-video-cpu-summary.json').read_text())
    if summary['original_carla_pixels_verified'] or summary['physical_signal_state_verified'] or len(summary['rows']) != 8:
        raise ValueError('Synthetic video scope differs')
    indexed = {(r['case'], r['candidate']): r for r in summary['rows']}
    if len(indexed) != 8:
        raise ValueError('Eight distinct video proofs required')
    compared = 0
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        pair = []
        for case in ('reference', 'contrast'):
            item = indexed[case, candidate]
            video = REPO / item['video_runtime_relative']
            source = HERE / 'synthetic-saved' / case / candidate
            receipt = source / 'signal-video-cpu.json'
            retained = json.loads(receipt.read_text())
            if not video.is_file() or item['video_sha256'] != sha(video) or item['receipt_sha256'] != sha(receipt):
                raise ValueError('Retained video or receipt hash differs')
            if item['negative_rejections'] != ['wrong_signal_color', 'wrong_native_frame_join']:
                raise ValueError('Required adversarial video checks absent')
            if retained['video_sha256'] != item['video_sha256'] or retained['native_samples_sha256'] != sha(source / 'native_samples.jsonl') or retained['video_frames_sha256'] != sha(source / 'video_frames.jsonl'):
                raise ValueError('Video source binding differs')
            if retained['original_carla_pixels_verified'] or retained['physical_signal_state_verified']:
                raise ValueError('Synthetic pixels promoted to physical proof')
            decoded = subprocess.run([str(FFMPEG), '-nostdin', '-hide_banner', '-loglevel', 'error',
                '-i', str(video), '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
            if decoded.returncode or len(decoded.stdout) != 480 * 16 * 16 * 3:
                raise ValueError('Independent full video decode differs')
            native = rows(source / 'native_samples.jsonl')
            mapping = rows(source / 'video_frames.jsonl')
            phase_colors = {'green': (0, 255, 0), 'yellow': (255, 255, 0), 'red': (255, 0, 0)}
            counts = {key: 0 for key in phase_colors}
            for i, (sample, frame) in enumerate(zip(native, mapping)):
                pixels = decoded.stdout[i * 768:(i + 1) * 768]
                if hashlib.sha256(pixels).hexdigest() != retained['decoded_frame_sha256'][i]:
                    raise ValueError('Decoded frame hash differs')
                phase = sample['observed_signal_state']
                if frame['video_frame'] != i or frame['native_frame'] != sample['native_frame'] or pixels != bytes(phase_colors[phase]) * 256:
                    raise ValueError('Decoded pixel, signal and Native frame join differs')
                counts[phase] += 1
            if retained['phase_counts'] != counts or retained['decoded_frames'] != 480:
                raise ValueError('Signal phase count differs')
            pair.append(native)
            compared += 1
        reference, contrast = pair
        if any(a['native_body_xy_m'] != b['native_body_xy_m'] or a['native_center_xy_m'] != b['native_center_xy_m'] for a, b in zip(reference, contrast)):
            raise ValueError('Controlled body path differs')
        entry = next(i for i, n in enumerate(reference) if min(p[1] for p in n['native_body_xy_m']) <= 7)
        if reference[entry]['observed_signal_state'] != 'yellow' or contrast[entry]['observed_signal_state'] != 'red':
            raise ValueError('Controlled decoded signal phase differs')
    return {'passed': True, 'decoded_bundles': compared, 'decoded_frames_per_bundle': 480,
            'controlled_pairs': 4, 'negative_rejections': 16,
            'summary_sha256': sha(HERE / 'signal-video-cpu-summary.json'),
            'original_carla_pixels_verified': False}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
