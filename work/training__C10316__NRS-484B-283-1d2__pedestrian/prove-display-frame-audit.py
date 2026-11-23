"""Generated FFV1/source-join positives and negatives for the display audit."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from audit_display_frames import audit  # noqa: E402

WIDTH, HEIGHT, FRAMES = 64, 48, 600


def lines(path, values):
    path.write_text(''.join(json.dumps(value, sort_keys=True) + '\n' for value in values))


def reject(attempt, expected):
    try:
        audit(attempt, FRAMES)
    except ValueError as error:
        assert expected in str(error), (expected, str(error))
    else:
        raise AssertionError('Damaged display source accepted')


def fixture(folder, count):
    folder.mkdir()
    raw = folder / 'raw.rgb'
    samples, mapping = [], []
    with raw.open('wb') as stream:
        for index in range(count):
            pixel = bytes((index % 256, (index * 3) % 256, (index * 7) % 256))
            data = pixel * (WIDTH * HEIGHT)
            stream.write(data)
            digest = hashlib.sha256(data).hexdigest()
            samples.append({'native_frame': index + 100, 'time_s': index / 20,
                            'original_display_frame_sha256': digest})
            mapping.append({'native_frame': index + 100, 'carla_frame': index + 100,
                            'video_frame': index, 'time_s': index / 20,
                            'source_rgb_sha256': {'display_close': digest}})
    command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
               '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{WIDTH}x{HEIGHT}',
               '-r', '20', '-i', str(raw), '-an', '-c:v', 'ffv1', '-level', '1',
               str(folder / 'display_close.mkv')]
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)
    raw.unlink()
    lines(folder / 'countdown_samples.jsonl', samples)
    lines(folder / 'video_frames.jsonl', mapping)
    return samples, mapping


def main():
    root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='display-audit-', dir=root) as directory:
        base = Path(directory)
        good = base / 'good'
        samples, mapping = fixture(good, FRAMES)
        result = audit(good, FRAMES)
        assert result['frames'] == FRAMES and result['pixel_integrity_verified']
        assert not result['signal_legibility_verified'] and not result['physical_acceptance_claimed']
        cli = subprocess.run([sys.executable, str(HERE / 'native/audit_display_frames.py'),
                              '--attempt', str(good), '--frames', str(FRAMES)],
                             capture_output=True, text=True, check=True, timeout=60)
        assert json.loads(cli.stdout) == result
        samples[17]['original_display_frame_sha256'] = '0' * 64
        lines(good / 'countdown_samples.jsonl', samples)
        reject(good, 'Original display RGB hash join differs at 17')
        samples[17]['original_display_frame_sha256'] = mapping[17]['source_rgb_sha256']['display_close']
        lines(good / 'countdown_samples.jsonl', samples)
        mapping[17]['native_frame'] += 1
        lines(good / 'video_frames.jsonl', mapping)
        reject(good, 'Display Native/video frame join differs at 17')
        mapping[17]['native_frame'] -= 1
        lines(good / 'video_frames.jsonl', mapping)
        bad_video = base / 'short_video'
        fixture(bad_video, FRAMES - 1)
        lines(bad_video / 'countdown_samples.jsonl', samples)
        lines(bad_video / 'video_frames.jsonl', mapping)
        reject(bad_video, 'Decoded display frame count differs')
        changed_video = base / 'changed_video'
        fixture(changed_video, FRAMES)
        changed_samples = [dict(row) for row in samples]
        changed_map = [dict(row) for row in mapping]
        changed_samples[0]['original_display_frame_sha256'] = samples[1]['original_display_frame_sha256']
        changed_map[0]['source_rgb_sha256'] = {
            'display_close': samples[1]['original_display_frame_sha256']}
        lines(changed_video / 'countdown_samples.jsonl', changed_samples)
        lines(changed_video / 'video_frames.jsonl', changed_map)
        reject(changed_video, 'Decoded display pixels differ at 0')
        assert audit(good, FRAMES) == result
    print(json.dumps({'passed': True, 'frames': FRAMES, 'negatives': 4,
                      'video_sha256': result['video_sha256'],
                      'scope': 'generated lossless video pixel integrity only; no signal legibility or governance claim'},
                     sort_keys=True))


if __name__ == '__main__':
    main()
