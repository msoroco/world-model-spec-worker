"""Build an explicit, source-hashed 600-frame CPU lighting fixture.

All pixels and kinematics remain synthetic diagnostics.  The law review still
requires original calibrated lamp, reach, discernibility, and time evidence.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[1]
RETAINED = ROOT / '.runtime-work/c230241-reference-saved-temporal'
TEMPLATE = ROOT / 'work/training__C394300__NRS-484B-223-3a__motor_vehicle_driver/selected-v2-source/controlled_1'
SCRATCH = ROOT / '.runtime-work/c230241-selected-video-hashes'
CAMERAS = [('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720),
           ('raw', 1920, 1080)]
FRAMES = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(value, separators=(',', ':')) + '\n' for value in values))


def build(case):
    dest = PACKAGE / 'selected-source' / case
    dest.mkdir(parents=True, exist_ok=True)
    if not SCRATCH.exists():
        SCRATCH.mkdir(parents=True)
    videos = []
    for name, width, height in CAMERAS:
        video = {'path': name + '.mkv', 'frames': FRAMES, 'width': width,
                 'height': height, 'fps': 20, 'color': 'black'}
        videos.append(video)
        target = SCRATCH / video['path']
        if not target.exists():
            subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                            '-f', 'lavfi', '-i', f'color=c=black:s={width}x{height}:r=20',
                            '-frames:v', str(FRAMES), '-an', '-c:v', 'ffv1', '-threads', '1',
                            '-fflags', '+bitexact', '-flags:v', '+bitexact', str(target)],
                           check=True, timeout=120)
    native = rows(RETAINED / 'native-lighting-frames.jsonl')
    mapping = rows(RETAINED / 'video_frames.jsonl')
    review = rows(RETAINED / 'lighting-review.jsonl')
    if len(native) != FRAMES or len(mapping) != FRAMES or len(review) != FRAMES:
        raise ValueError('Retained lighting rows are incomplete')
    for i in range(FRAMES):
        for row in (native[i], mapping[i], review[i]):
            row['native_frame'] = i
        mapping[i]['carla_frame'] = i
        if case == 'contrast':
            native[i]['light_state_observed'] = 1
            review[i]['headlamp_lit'] = False
    write_rows(dest / 'native-lighting-frames.jsonl', native)
    write_rows(dest / 'video_frames.jsonl', mapping)
    write_rows(dest / 'lighting-review.jsonl', review)
    context = json.loads((RETAINED / 'lighting-review-context.json').read_text())
    context['source_sha256'] = {name: sha(SCRATCH / (name + '.mkv'))
                                for name, _, _ in CAMERAS}
    context['source_sha256']['native-lighting-frames.jsonl'] = sha(dest / 'native-lighting-frames.jsonl')
    context['source_sha256']['video_frames.jsonl'] = sha(dest / 'video_frames.jsonl')
    write(dest / 'lighting-review-context.json', context)
    shutil.copyfile(RETAINED / 'lighting-measure-context.json',
                    dest / 'lighting-measure-context.json')
    # Neutral, explicit Core media/capture rows.  A prior synthetic map is
    # used only to exercise the adapter and cannot establish lighting law.
    for name in ('road.xodr', 'scene.xodr', 'capture/recorder_info.txt'):
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TEMPLATE / name, target)
    template_trace = rows(TEMPLATE / 'trace.jsonl')[0]
    template_evidence = rows(TEMPLATE / 'capture/evidence.jsonl')[0]
    trace, evidence, native_frames = [], [], []
    for i in range(FRAMES):
        time = i / 20
        x = -95 + i * 0.1
        state = json.loads(json.dumps(template_trace))
        state.update(frame=i, time_s=time, position={'x': x, 'y': 3.5, 'z': 0.5},
                     position_m=[x, 3.5, 0.5], speed_mps=2,
                     speed_mph=4.473872, velocity_mps=[2, 0, 0])
        trace.append(state)
        item = json.loads(json.dumps(template_evidence))
        item.update(original_frame=i, replay_frame=i, recording_time_s=time,
                    replay_simulation_time_s=time, actor_id=107)
        item['ego']['position_m'] = [x, 3.5, 0.5]
        item['ego']['speed_mps'] = 2
        evidence.append(item)
        native_frames.append({'frame': i, 'time_s': time,
                              'simulation_time': time, 'synthetic_diagnostic': True,
                              'adapter_graph': f'graphs/base/{i:08d}.adapter.json'})
    write_rows(dest / 'trace.jsonl', trace)
    write_rows(dest / 'capture/evidence.jsonl', evidence)
    write_rows(dest / 'capture/native/frames.jsonl', native_frames)
    write_rows(dest / 'channels/kin.position.jsonl',
               [{'frame': i, 'time_s': i/20, 'value': trace[i]['position_m'],
                 'source_kind': 'synthetic_native_sample'} for i in range(FRAMES)])
    write_rows(dest / 'channels/kin.speed.jsonl',
               [{'frame': i, 'time_s': i/20, 'value': 2,
                 'source_kind': 'synthetic_native_sample'} for i in range(FRAMES)])
    write(dest / 'capture/manifest.json',
          {'extraction_confirmed': True, 'frames': FRAMES,
           'required_observations': [], 'synthetic_diagnostic': True,
           'sources': {'road.xodr': sha(dest / 'road.xodr'),
                       'trace.jsonl': sha(dest / 'trace.jsonl')}})
    write(dest / 'acquisition-provenance.json',
          {'provenance_kind': 'synthetic_local_diagnostic', 'diagnostic_fixture': True,
           'native_executed': False})
    graphs = [{'path': f'capture/native/graphs/base/{i:08d}.adapter.json',
               'attributes': {'frame': i}, 'nodes': [], 'edges': []}
              for i in range(FRAMES)]
    spec = {'files': {}, 'graphs': graphs, 'videos': videos}
    spec_path = PACKAGE / f'selected-generator-{case}.json'
    spec_path.write_text(json.dumps(spec, separators=(',', ':')) + '\n')
    sources = []
    for path in sorted(dest.rglob('*')):
        if path.is_file():
            if path.stat().st_size > 2*1024*1024:
                raise ValueError('Returned source exceeds 2 MiB: ' + str(path))
            sources.append({'path': str(path.relative_to(dest)),
                            'source': str(path.relative_to(ROOT)),
                            'sha256': sha(path)})
    recipe_path = PACKAGE / f'selected-recipe-{case}.json'
    write(recipe_path, {'format': 'worker-fixture-recipe', 'sources': sources,
                        'generator': {'source': str(spec_path.relative_to(ROOT)),
                                      'sha256': sha(spec_path)}})
    return {'case': case, 'sources': len(sources), 'graphs': len(graphs),
            'generator_sha256': sha(spec_path), 'recipe_sha256': sha(recipe_path)}


if __name__ == '__main__':
    print(json.dumps([build(case) for case in ('reference', 'contrast')]))
