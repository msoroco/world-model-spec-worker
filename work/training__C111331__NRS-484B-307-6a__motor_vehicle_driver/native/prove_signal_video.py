"""Exercise exact 480-frame synthetic FFV1 signal video and negatives."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from signal_video_cpu import COLORS, FRAME_BYTES, inspect

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FFMPEG = REPO / '.runtime-work/linux_arm64/ffmpeg'
MEDIA = REPO / '.runtime-work/c111331-signal-cpu-video'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def emit(video, phases):
    video.parent.mkdir(parents=True, exist_ok=True)
    if video.exists():
        video.unlink()
    process = subprocess.Popen([str(FFMPEG), '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '16x16', '-r', '20', '-i', 'pipe:0',
        '-an', '-c:v', 'ffv1', '-level', '1', str(video)], stdin=subprocess.PIPE,
        stderr=subprocess.PIPE)
    for phase in phases:
        process.stdin.write(bytes(COLORS[phase]) * (FRAME_BYTES // 3))
    process.stdin.close()
    error = process.stderr.read()
    if process.wait(timeout=120):
        raise RuntimeError('Synthetic FFV1 encode failed: ' + error.decode(errors='replace')[-500:])


def prove():
    if not FFMPEG.is_file():
        raise FileNotFoundError(FFMPEG)
    results = []
    for case in ('reference', 'contrast'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            source = HERE / 'synthetic-saved' / case / candidate
            native = [json.loads(line) for line in (source / 'native_samples.jsonl').read_text().splitlines()]
            phases = [row['observed_signal_state'] for row in native]
            video = MEDIA / case / candidate / 'signal_reference.mkv'
            emit(video, phases)
            result = inspect(source, video, FFMPEG)
            if result['decoded_frames'] != 480 or result['original_carla_pixels_verified']:
                raise AssertionError('Synthetic video scope differs')
            receipt = source / 'signal-video-cpu.json'
            receipt.write_text(json.dumps(result, indent=2) + '\n')
            negatives = []
            changed = list(phases)
            changed[200] = 'green' if phases[200] != 'green' else 'red'
            bad_video = MEDIA / case / candidate / 'changed_signal.mkv'
            emit(bad_video, changed)
            try:
                inspect(source, bad_video, FFMPEG)
            except ValueError as exc:
                if 'disagrees with saved Native phase' not in str(exc):
                    raise
                negatives.append('wrong_signal_color')
            else:
                raise AssertionError('Wrong signal color accepted')
            bad_video.unlink()
            bad = MEDIA / case / candidate / 'bad_source'
            if bad.exists():
                shutil.rmtree(bad)
            bad.mkdir()
            shutil.copy2(source / 'native_samples.jsonl', bad / 'native_samples.jsonl')
            mapping = [json.loads(line) for line in (source / 'video_frames.jsonl').read_text().splitlines()]
            mapping[200]['native_frame'] = -1
            (bad / 'video_frames.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in mapping))
            try:
                inspect(bad, video, FFMPEG)
            except ValueError as exc:
                if 'frame join differs' not in str(exc):
                    raise
                negatives.append('wrong_native_frame_join')
            else:
                raise AssertionError('Broken video frame join accepted')
            shutil.rmtree(bad)
            results.append({'case': case, 'candidate': candidate,
                            'video_runtime_relative': str(video.relative_to(REPO)),
                            'video_sha256': sha(video), 'receipt_sha256': sha(receipt),
                            'negative_rejections': negatives})
    output = {'format': 'c111331-synthetic-signal-video-proof-v1',
              'rows': results, 'original_carla_pixels_verified': False,
              'physical_signal_state_verified': False}
    (HERE / 'signal-video-cpu-summary.json').write_text(json.dumps(output, indent=2) + '\n')
    return {'passed': True, 'bundles': len(results), 'negative_rejections': 2 * len(results),
            'summary_sha256': sha(HERE / 'signal-video-cpu-summary.json')}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
