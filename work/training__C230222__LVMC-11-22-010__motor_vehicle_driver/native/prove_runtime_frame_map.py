"""Prove C230222 observation against rows written by the pinned FrameMap."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = ROOT / '.runtime-work/c230222-runtime-frame-map-v1'
RUNTIME = ROOT / 'runtime/pipeline/scenario_pipeline'
assert Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve().is_relative_to(
    (ROOT / '.runtime-work').resolve())
sys.path.insert(0, str(RUNTIME))
from worker_exchange.native_output import FrameMap  # noqa: E402

spec = importlib.util.spec_from_file_location('attention_observer', HERE / 'attention_observation.py')
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


def main():
    if OUTPUT.exists():
        raise ValueError('Use a fresh ignored integration fixture directory')
    OUTPUT.mkdir(parents=True)
    cameras = {}
    for view in observer.VIEWS:
        path = OUTPUT / (view + '.mkv')
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                        '-f', 'lavfi', '-i', 'color=c=black:s=16x16:r=20',
                        '-frames:v', '600', '-an', '-c:v', 'ffv1', str(path)], check=True)
        cameras[view] = path.name
    (OUTPUT / 'native-driving-context.json').write_text(json.dumps({
        'source_kind': 'synthetic_native_sample', 'camera_sources': cameras}) + '\n')
    with (OUTPUT / 'native-ego-frames.jsonl').open('x') as trace, \
            FrameMap(OUTPUT / 'video_frames.jsonl') as mapping:
        for i in range(observer.FRAMES):
            native = 1200 + i
            trace.write(json.dumps({'source_kind': 'synthetic_native_sample',
                                    'native_frame': native, 'time_s': i / observer.RATE,
                                    'position_m': [i * 0.1, 0.0, 0.0],
                                    'velocity_mps': [2.0, 0.0, 0.0],
                                    'acceleration_mps2': [0.0, 0.0, 0.0],
                                    'yaw_deg': 0.0}) + '\n')
            mapping.append(native, i / observer.RATE)
    measured = observer.measure(OUTPUT)
    assert measured['sample_count'] == 600
    assert measured['source_kind'] == 'synthetic_native_sample'
    assert measured['driver_attention_to_operation'] is None
    assert measured['legal_verdict'] is None
    assert len(measured['camera_decode']) == 4
    print(json.dumps({'passed': True, 'writer': 'pinned FrameMap',
                      'observer_format': measured['format'], 'joined_frames': 600,
                      'decoded_cameras': 4, 'source_kind': 'synthetic_native_sample',
                      'attention_conclusion': None, 'legal_verdict': None}))


if __name__ == '__main__':
    main()
