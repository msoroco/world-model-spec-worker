"""Source-shaped CPU positive and negative checks for saved-only joins."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from finalize import verify_source_joins
from prove_stop_yield import fixture
from stop_yield_saved_measure import measure


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def rejects(operation, fragment):
    try:
        operation()
    except ValueError as exc:
        if fragment not in str(exc):
            raise AssertionError(str(exc)) from exc
    else:
        raise AssertionError('Invalid saved source passed')


def main():
    scratch = Path(__file__).resolve().parents[2] / '.runtime-work'
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='nrs2572-saved-', dir=scratch) as temp:
        root = Path(temp)
        packet, controls = fixture()
        for i, row in enumerate(packet['frames']):
            row['native_frame'] = i + 100
            row['source_cameras'] = {name: i + 100 for name in
                ('overview', 'approach', 'reference_corner', 'driver_reference')}
        observed = measure(json.dumps(packet).encode(), json.dumps(controls).encode())
        write_rows(root / 'video_frames.jsonl', [
            {'video_frame': i, 'carla_frame': row['native_frame'], 'time_s': row['t_s'],
             'source_cameras': row['source_cameras']} for i, row in enumerate(packet['frames'])])
        write_rows(root / 'trace.jsonl', [
            {'frame': row['native_frame'], 'time_s': row['t_s']} for row in packet['frames']])
        for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
            (root / (name + '.mkv')).write_bytes(b'CPU placeholder; ffprobe mocked')
        with patch('finalize.subprocess.check_output', return_value='600\n'):
            verify_source_joins(root, packet, observed)
            video = root / 'video_frames.jsonl'
            rows = [json.loads(line) for line in video.read_text().splitlines()]
            rows[13]['carla_frame'] += 1
            write_rows(video, rows)
            rejects(lambda: verify_source_joins(root, packet, observed), 'frame join differs')
            rows[13]['carla_frame'] -= 1
            write_rows(video, rows)
            (root / 'trace.jsonl').unlink()
            rejects(lambda: verify_source_joins(root, packet, observed), 'Missing required saved source')
    print('saved-only 600-frame Core/body/video join passes; changed frame and missing trace reject')


if __name__ == '__main__':
    main()
