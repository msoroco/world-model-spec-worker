"""Synthetic diagnostic tests for display pixel activity, without Native claims."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('activity', HERE / 'native/audit_display_activity.py')
activity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(activity)


def generate(folder, mode):
    folder.mkdir()
    rows = []
    encoder = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
        '-n', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '64x64', '-r', '20',
        '-i', 'pipe:0', '-an', '-c:v', 'ffv1', str(folder / 'display_close.mkv')],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for index in range(600):
        flashing = index < 200
        lit = (index // 5) % 2 == 0 if flashing else True
        rows.append({'native_frame': 1000 + index,
            'display_illuminated': lit,
            'indication': 'dont_walk_flashing' if flashing else 'dont_walk_steady'})
        value = 255 if (lit and mode == 'aligned') or (not lit and mode == 'inverted') else 0
        if mode == 'blank':
            value = 0
        row = bytes([0, 0, 0] * 16 + [value, value, value] * 32 + [0, 0, 0] * 16)
        frame = bytes([0, 0, 0] * 64) * 16 + row * 32 + bytes([0, 0, 0] * 64) * 16
        encoder.stdin.write(frame)
    encoder.stdin.close()
    error = encoder.stderr.read()
    if encoder.wait(timeout=120):
        raise RuntimeError('Synthetic encoder failed: ' + error.decode()[:200])
    (folder / 'countdown_samples.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))


def main():
    root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='display-activity-', dir=root) as temp:
        temp = Path(temp)
        good = temp / 'aligned'
        generate(good, 'aligned')
        proof = activity.audit(good, (16, 16, 32, 32))
        assert proof['pixel_activity_verified'] and not proof['digit_legibility_verified']
        negatives = {}
        for mode in ('blank', 'inverted'):
            folder = temp / mode
            generate(folder, mode)
            try:
                activity.audit(folder, (16, 16, 32, 32))
            except ValueError as exc:
                assert 'do not follow illumination' in str(exc)
                negatives[mode] = str(exc)
            else:
                raise AssertionError(mode + ' was accepted')
        rows = (good / 'countdown_samples.jsonl').read_text().splitlines()
        (good / 'countdown_samples.jsonl').write_text('\n'.join(rows[:-1]) + '\n')
        try:
            activity.audit(good, (16, 16, 32, 32))
        except ValueError as exc:
            assert 'full 30-second source' in str(exc)
            negatives['truncated_source'] = str(exc)
        else:
            raise AssertionError('truncated source was accepted')
    stable = {key: value for key, value in proof.items()
              if key not in ('video_sha256', 'samples_sha256')}
    print(json.dumps({'passed': True, 'positive': stable, 'negatives': negatives,
        'native_capture_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
