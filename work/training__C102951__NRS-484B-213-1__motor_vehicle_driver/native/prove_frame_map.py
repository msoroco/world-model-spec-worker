"""Check pinned FrameMap identity fields consumed by saved processing."""
import hashlib
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
if not output_root.is_relative_to(ROOT/'.runtime-work'):
    raise ValueError('Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first')
sys.path.insert(0, str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.native_output import FrameMap


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    with TemporaryDirectory(dir=ROOT/'.runtime-work', prefix='c102951-frame-map-') as folder:
        path = Path(folder)/'video_frames.jsonl'
        with FrameMap(path) as source:
            for index in range(600):
                source.append(1000+index, (index+1)/20)
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        if len(rows) != 600 or any(
                row['video_frame'] != index or
                row['carla_frame'] != row['native_frame'] or
                row['native_frame'] != 1000+index or
                abs(row['time_s']-(index+1)/20) > 1e-9
                for index, row in enumerate(rows)):
            raise ValueError('Pinned FrameMap lacks full 600-frame saved join')
        try:
            with FrameMap(Path(folder)/'duplicate.jsonl') as source:
                source.append(1, .05)
                source.append(1, .10)
        except ValueError as error:
            if 'Original frames/times must increase' not in str(error):
                raise
        else:
            raise ValueError('Repeated original frame accepted')
    runner = (HERE/'runner.py').read_text()
    if "FrameMap(output/'video_frames.jsonl')" not in runner or 'frame_map.append(frame, time_s)' not in runner:
        raise ValueError('Native runner does not use pinned FrameMap')
    return {'format': 'c102951-pinned-frame-map-cpu-proof-v1',
            'frame_count': 600, 'rate_hz': 20,
            'first_carla_frame': 1000, 'last_carla_frame': 1599,
            'duplicate_frame_rejected': True,
            'runner_sha256': sha(HERE/'runner.py'),
            'preparer_sha256': sha(HERE/'prepare_pass.py'),
            'original_native_observed': False, 'delivery_ready': False}


if __name__ == '__main__':
    result = prove()
    (HERE/'frame-map-proof.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
