"""Exercise the full-window source observer with synthetic Native-shaped rows."""
import importlib.util
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = ROOT / '.runtime-work/c230222-attention-observation-v1'
spec = importlib.util.spec_from_file_location('observer', HERE / 'attention_observation.py')
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))


def main():
    if OUTPUT.exists():
        raise ValueError('Use a fresh ignored synthetic fixture directory')
    OUTPUT.mkdir(parents=True)
    cameras = {}
    for view in observer.VIEWS:
        path = OUTPUT / (view + '.mkv')
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                        '-f', 'lavfi', '-i', 'color=c=black:s=16x16:r=20',
                        '-frames:v', '600', '-an', '-c:v', 'ffv1', str(path)], check=True)
        cameras[view] = path.name
    (OUTPUT / 'native-driving-context.json').write_text(json.dumps({
        'source_kind': 'synthetic_native_sample', 'camera_sources': cameras,
        'driver_facing_pixels_reviewed': False}) + '\n')
    trace = []
    mapping = []
    for i in range(observer.FRAMES):
        trace.append({'source_kind': 'synthetic_native_sample', 'native_frame': 900 + i,
                      'time_s': i / 20, 'position_m': [i * 0.1, 0.0, 0.0],
                      'velocity_mps': [2.0, 0.0, 0.0],
                      'acceleration_mps2': [0.0, 0.0, 0.0],
                      'yaw_deg': 179.0 if i == 0 else -179.0})
        mapping.append({'native_frame': 900 + i, 'video_frame': i, 'time_s': i / 20})
    trace_path = OUTPUT / 'native-ego-frames.jsonl'
    map_path = OUTPUT / 'video_frames.jsonl'
    write_rows(trace_path, trace)
    write_rows(map_path, mapping)
    result = observer.measure(OUTPUT)
    assert result['sample_count'] == 600 and result['driver_attention_to_operation'] is None
    assert result['measurements']['ego_yaw_rate'][1] == 40.0
    assert all(speed == 2.0 for speed in result['measurements']['ego_speed'])
    assert result['legal_verdict'] is None and result['source_kind'] == 'synthetic_native_sample'
    mapping[-1]['native_frame'] += 1
    write_rows(map_path, mapping)
    try:
        observer.measure(OUTPUT)
    except ValueError as error:
        assert 'frame join differs' in str(error)
    else:
        raise AssertionError('Corrupt frame join accepted')
    write_rows(map_path, mapping[:-1])
    try:
        observer.measure(OUTPUT)
    except ValueError as error:
        assert 'Complete 600-frame' in str(error)
    else:
        raise AssertionError('Truncated frame map accepted')
    print(json.dumps({'passed': True, 'frames_measured': 600,
                      'negative_frame_join_rejected': True,
                      'negative_truncation_rejected': True,
                      'attention_conclusion': None,
                      'source_kind': 'synthetic_native_sample'}))


if __name__ == '__main__':
    main()
