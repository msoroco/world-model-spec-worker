"""Build an explicitly synthetic public compatibility source for condition A.

All video generation happens in .runtime-work. The selected-source files here
are diagnostic text fixtures and never represent an observed railroad.
"""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from prove_rail_source import CASE, CAMERAS, fixture


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parents[1]
SOURCE = PACKAGE / 'selected-source/condition_a'
SCRATCH = ROOT / '.runtime-work'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def main():
    if SOURCE.exists():
        raise ValueError('Retain prior diagnostic source; remove only after deliberate review')
    SCRATCH.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=SCRATCH, prefix='c229398-public-source-') as tmp:
        stage = Path(tmp)
        fixture(stage)
        source_package = ROOT / 'work/training__C135709__NRS-484B-510__motor_vehicle_driver'
        graph_spec = json.loads((source_package / 'selected-generator-witness_1.json').read_text())
        (stage / 'road.xodr').write_bytes((source_package / 'selected-source/witness_1/road.xodr').read_bytes())
        rows = [json.loads(x) for x in (stage / 'video_frames.jsonl').read_text().splitlines()]
        actor_rows = [json.loads(x) for x in (stage / 'original-native-rows.jsonl').read_text().splitlines()]
        for index, row in enumerate(rows):
            frame = 100 + index
            row['native_frame'] = frame
            row['camera_native_frames'] = {name: frame for name in CAMERAS}
            row['carla_frame'] = row['native_frame']
            actor_rows[index]['native_frame'] = frame
            for key in ('pose_source_ref', 'extent_source_ref', 'speed_source_ref'):
                actor_rows[index][key] = actor_rows[index][key] + ':' + str(frame)
        (stage / 'video_frames.jsonl').write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in rows))
        (stage / 'original-native-rows.jsonl').write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in actor_rows))
        trace = []
        evidence = []
        native_frames = []
        for index, row in enumerate(rows):
            frame, time_s = row['native_frame'], row['time_s']
            x, y = -12.0, -3.0
            trace.append({'frame': frame, 'time_s': time_s, 'position': {'x': x, 'y': y, 'z': 1.0},
                          'position_m': [x, y], 'heading_deg': 0.0, 'speed_mps': 0.0,
                          'speed_mph': 0.0, 'velocity_mps': [0.0, 0.0, 0.0],
                          'control': {'throttle': 0.0, 'brake': 1.0}})
            body = [[x+dx, y+dy, dz] for dx in (-2.0, 2.0)
                    for dy in (-1.0, 1.0) for dz in (0.0, 1.5)]
            evidence.append({'actor_id': 42, 'ego': {'body_vertices_m': body,
                            'heading_deg': 0.0, 'position_m': [x, y, 1.0],
                            'speed_mps': 0.0, 'speed_provenance': 'synthetic_native_sample'},
                            'original_frame': frame, 'recording_time_s': time_s,
                            'replay_frame': frame, 'replay_simulation_time_s': time_s,
                            'world': {'road_projection': {'road_id': 1, 'section_id': 0,
                                      'lane_id': -1, 's_m': 10.0}, 'weather': {}}})
            native_frames.append({'adapter_graph': f'graphs/base/{frame:08d}.adapter.json',
                                  'frame': frame, 'simulation_time': time_s,
                                  'synthetic_diagnostic': True, 'time_s': time_s})
        for name, values in [('trace.jsonl', trace), ('capture/evidence.jsonl', evidence),
                             ('capture/native/frames.jsonl', native_frames)]:
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in values))
        (stage / 'capture/recorder_info.txt').write_text('Synthetic diagnostic fixture; no CARLA recorder. Create 42: vehicle.tesla.model3\n')
        write(stage / 'acquisition-provenance.json',
              {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
               'physical_acceptance_claimed': False})
        write(stage / 'capture/manifest.json', {'case_id': CASE, 'frames': 600,
              'extraction_confirmed': True, 'synthetic_diagnostic': True,
              'required_observations': ['kin.extent', 'kin.velocity'],
              'sources': {'trace.jsonl': sha(stage / 'trace.jsonl'),
                          'road.xodr': sha(stage / 'road.xodr')}})
        videos = [{'path': name + '.mkv', 'frames': 600,
                   'width': 1920 if name == 'overview' else 1280,
                   'height': 1080 if name == 'overview' else 720,
                   'fps': 20, 'color': color}
                  for name, color in zip(CAMERAS, ('blue', 'green', 'white', 'red'))]
        for item in videos:
            target = stage / item['path']
            target.unlink()
            subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                            '-n', '-f', 'lavfi', '-i',
                            f"color=c={item['color']}:s={item['width']}x{item['height']}:r=20",
                            '-frames:v', '600', '-an', '-c:v', 'ffv1', '-threads', '1',
                            '-fflags', '+bitexact', '-flags:v', '+bitexact', str(target)],
                           check=True, timeout=120)
        seal_names = ['original-rail-survey.json', 'original-native-rows.jsonl',
                      'video_frames.jsonl'] + [name + '.mkv' for name in CAMERAS]
        write(stage / 'original-source-seal.json',
              {'format': 'diagnostic-rail-source-shape-seal', 'case_id': CASE,
               'sha256': {name: sha(stage / name) for name in seal_names}})
        closure = seal_names + ['original-source-seal.json', 'trace.jsonl',
                                'capture/manifest.json']
        write(stage / 'capture-seal.json', {'format': 'worker-sealed-capture',
              'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
              'frames': 600, 'restoration': {'restored': True},
              'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
              'sources': {name: sha(stage / name) for name in closure}})
        SOURCE.mkdir(parents=True)
        source_items = []
        for path in sorted(stage.rglob('*')):
            if not path.is_file() or path.suffix == '.mkv':
                continue
            relative = path.relative_to(stage)
            target = SOURCE / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            source_items.append({'path': str(relative), 'source': str(target.relative_to(ROOT)),
                                 'sha256': sha(target)})
        generator = {'files': {}, 'graphs': graph_spec['graphs'], 'videos': videos}
        generator_path = PACKAGE / 'selected-generator-condition_a.json'
        generator_path.write_text(json.dumps(generator, separators=(',', ':')) + '\n')
        recipe = {'format': 'worker-fixture-recipe', 'generator':
                  {'source': str(generator_path.relative_to(ROOT)),
                   'sha256': sha(generator_path)}, 'sources': source_items}
        recipe_path = PACKAGE / 'selected-recipe-condition_a.json'
        recipe_path.write_text(json.dumps(recipe, separators=(',', ':')) + '\n')
        print(json.dumps({'case_id': CASE, 'source_count': len(source_items),
                          'generator_sha256': sha(generator_path),
                          'recipe_sha256': sha(recipe_path),
                          'original_native_observed': False}))


if __name__ == '__main__':
    main()
