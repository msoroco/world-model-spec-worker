"""Repackage saved synthetic distance probes as explicit-source v2 recipes."""
import hashlib
import json
import math
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = ('below_50_ft', 'at_50_ft', 'above_50_ft')
CAMERAS = (('overview', 1920, 1080, 'blue'), ('approach', 1280, 720, 'green'),
           ('reference_corner', 1280, 720, 'white'), ('driver_reference', 1280, 720, 'red'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_attempt(case):
    path = ROOT / '.runtime-work/c3943003c-600-base' / case
    if not path.is_dir():
        raise ValueError('Saved synthetic source missing')
    return path


def build(case):
    source = source_attempt(case)
    destination = HERE / 'selected-v2-source' / case
    destination.mkdir(parents=True, exist_ok=True)
    names = ['trace.jsonl', 'video_frames.jsonl', 'native_samples.jsonl',
             'body_history.jsonl', 'road_geometry.json', 'road.xodr',
             'context.json',
             'capture/manifest.json', 'capture/recorder_info.txt',
             'capture/evidence.jsonl', 'capture/native/frames.jsonl']
    names.extend(str(p.relative_to(source)) for p in sorted((source / 'channels').glob('*.jsonl')))
    native = [json.loads(line) for line in (source / 'native_samples.jsonl').read_text().splitlines()]
    if len(native) != 600:
        raise ValueError('Synthetic Native sample count differs')
    velocities = []
    for index, row in enumerate(native):
        before, after = (native[0], native[1]) if index == 0 else (native[index - 1], row)
        dt = after['time_s'] - before['time_s']
        if dt <= 0:
            raise ValueError('Synthetic sample time is not increasing')
        xy0, xy1 = before['native_center_xy_m'], after['native_center_xy_m']
        velocity = [(xy1[0] - xy0[0]) / dt, (xy1[1] - xy0[1]) / dt, 0.0]
        if not all(math.isfinite(value) for value in velocity):
            raise ValueError('Synthetic velocity is nonfinite')
        velocities.append(velocity)
    sources = []
    frame_ids = []
    for name in names:
        src = source / name
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if name == 'capture/native/frames.jsonl':
            rows = [json.loads(line) for line in src.read_text().splitlines()]
            if len(rows) != 600:
                raise ValueError('Original synthetic frame count differs')
            for row in rows:
                frame = row['frame']
                frame_ids.append(frame)
                row.pop('base', None)
                row.pop('abstract', None)
                row['adapter_graph'] = f'graphs/base/{frame:08d}.adapter.json'
            target.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        elif name in ('trace.jsonl', 'native_samples.jsonl', 'capture/evidence.jsonl'):
            data = [json.loads(line) for line in src.read_text().splitlines()]
            if len(data) != 600:
                raise ValueError('Synthetic source row count differs')
            for index, row in enumerate(data):
                velocity = velocities[index]
                speed = math.hypot(velocity[0], velocity[1])
                if name == 'trace.jsonl':
                    row['velocity_mps'] = velocity
                    row['speed_mps'] = speed
                    row['speed_mph'] = speed * 2.2369362921
                    row['speed_provenance'] = 'synthetic_native_sample'
                elif name == 'native_samples.jsonl':
                    row['speed_mps'] = speed
                    row['speed_provenance'] = 'synthetic_native_sample'
                else:
                    row['ego']['speed_mps'] = speed
                    row['ego']['speed_provenance'] = 'synthetic_native_sample'
            target.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in data))
        elif name == 'capture/manifest.json':
            meta = json.loads(src.read_text())
            meta['sources']['trace.jsonl'] = sha(destination / 'trace.jsonl')
            meta['synthetic_speed_provenance'] = 'position_derived_for_current_runtime'
            target.write_text(json.dumps(meta) + '\n')
        else:
            shutil.copyfile(src, target)
        if target.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Returned text source exceeds 2 MiB')
        sources.append({'path': name, 'source': str(target.relative_to(ROOT)),
                        'sha256': sha(target)})
    if len(set(frame_ids)) != 600 or frame_ids != list(range(frame_ids[0], frame_ids[0] + 600)):
        raise ValueError('Synthetic source frame IDs are not contiguous')
    provenance = destination / 'acquisition-provenance.json'
    provenance.write_text(json.dumps({'provenance_kind': 'synthetic_local_diagnostic',
                                      'diagnostic_fixture': True, 'native_executed': False}) + '\n')
    sources.append({'path': 'acquisition-provenance.json',
                    'source': str(provenance.relative_to(ROOT)), 'sha256': sha(provenance)})
    graphs = [{'path': f'capture/native/graphs/base/{frame:08d}.adapter.json',
               'attributes': {'frame': frame}, 'nodes': [], 'edges': []}
              for frame in frame_ids]
    videos = [{'path': name + '.mkv', 'frames': 600, 'width': width,
               'height': height, 'fps': 20, 'color': color}
              for name, width, height, color in CAMERAS]
    spec = {'files': {}, 'graphs': graphs, 'videos': videos}
    spec_path = HERE / f'selected-v2-{case}-generator.json'
    spec_path.write_text(json.dumps(spec, separators=(',', ':')) + '\n')
    if spec_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Generator spec exceeds 2 MiB')
    recipe = {'format': 'worker-fixture-recipe', 'sources': sources,
              'generator': {'source': str(spec_path.relative_to(ROOT)),
                            'sha256': sha(spec_path)}}
    recipe_path = HERE / f'selected-v2-{case}-recipe.json'
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    return {'case': case, 'source_count': len(sources),
            'frame_count': len(frame_ids), 'recipe_sha256': sha(recipe_path)}


if __name__ == '__main__':
    print(json.dumps([build(case) for case in CASES]))
