"""Preserve source-only 600-frame diagnostic inputs as current v2 recipes."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RAW = ('native_samples.jsonl', 'video_frames.jsonl', 'pixel_review.jsonl',
       'trace.jsonl', 'capture/evidence.jsonl', 'body_history.jsonl',
       'capture/native/frames.jsonl', 'road.xodr',
       'capture/recorder_info.txt', 'capture/manifest.json',
       'sign-review.json')
CAMERAS = (('overview', 1920, 1080, 'blue'),
           ('approach', 1280, 720, 'green'),
           ('reference_corner', 1280, 720, 'white'),
           ('sign_reference', 1280, 720, 'white'),
           ('driver_reference', 1280, 720, 'red'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(case):
    log = json.loads((HERE / f'source-only-core-{case}-primary.log').read_text())
    source = Path(log['scratch']) / 'attempt'
    destination = HERE / 'v2-source' / case
    destination.mkdir(parents=True, exist_ok=True)
    scratch = ROOT / '.runtime-work/c104538-v2'
    scratch.mkdir(parents=True, exist_ok=True)
    approach = scratch / 'approach-seed.mkv'
    if not approach.exists():
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                        '-f', 'lavfi', '-i', 'color=c=green:s=1280x720:r=20',
                        '-frames:v', '600', '-an', '-c:v', 'ffv1', '-threads', '1',
                        '-fflags', '+bitexact', '-flags:v', '+bitexact', str(approach)],
                       check=True, timeout=120)
    items = []
    for name in RAW:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if name == 'sign-review.json':
            review = json.loads((source / name).read_text())
            review['video_sha256'] = sha(approach)
            target.write_text(json.dumps(review) + '\n')
        elif name == 'trace.jsonl':
            # The current renderer independently derives speed from original
            # velocity. This fixture source is synthetic, so give every saved
            # row a velocity vector consistent with its declared speed/heading.
            rows = []
            for line in (source / name).read_text().splitlines():
                row = json.loads(line)
                speed = float(row['speed_mps'])
                heading = math.radians(float(row['heading_deg']))
                row['velocity_mps'] = [speed * math.cos(heading), speed * math.sin(heading), 0.0]
                rows.append(json.dumps(row, separators=(',', ':')))
            target.write_text('\n'.join(rows) + '\n')
        elif name == 'capture/manifest.json':
            manifest = json.loads((source / name).read_text())
            manifest['sources']['trace.jsonl'] = sha(destination / 'trace.jsonl')
            target.write_text(json.dumps(manifest, separators=(',', ':')) + '\n')
        else:
            shutil.copyfile(source / name, target)
        if target.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Source exceeds 2 MiB: ' + name)
        items.append({'path': name, 'source': str(target.relative_to(ROOT)),
                      'sha256': sha(target)})
    frames = [json.loads(line) for line in
              (source / 'capture/native/frames.jsonl').read_text().splitlines()]
    assert len(frames) == 600
    graphs = []
    for frame in frames:
        name = 'capture/native/' + frame['adapter_graph']
        graph = json.loads((source / name).read_text())
        assert graph['format'] == 'native-adapter-graph-v1'
        assert graph['metadata']['frame'] == frame['frame']
        graphs.append({'path': name, 'attributes': graph['metadata'],
                       'nodes': graph['nodes'], 'edges': graph['edges']})
    videos = [{'path': name + '.mkv', 'frames': 600, 'width': width,
               'height': height, 'fps': 20, 'color': color}
              for name, width, height, color in CAMERAS]
    spec = {'files': {}, 'graphs': graphs, 'videos': videos}
    spec_path = HERE / f'v2-{case}-generator.json'
    spec_path.write_text(json.dumps(spec, separators=(',', ':')) + '\n')
    if spec_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Graph generator exceeds 2 MiB')
    recipe = {'format': 'worker-fixture-recipe', 'sources': items,
              'generator': {'source': str(spec_path.relative_to(ROOT)),
                            'sha256': sha(spec_path)}}
    recipe_path = HERE / f'v2-{case}-recipe.json'
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    return {'case': case, 'source_count': len(items), 'graphs': len(graphs),
            'videos': len(videos),
            'recipe_sha256': sha(recipe_path), 'generator_sha256': sha(spec_path)}


if __name__ == '__main__':
    print(json.dumps([build(case) for case in ('witness_1', 'witness_2')]))
