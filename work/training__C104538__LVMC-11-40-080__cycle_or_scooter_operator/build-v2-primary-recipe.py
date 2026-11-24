"""Freeze raw synthetic rider sources into a current v2 fixture recipe."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RAW = ('native_samples.jsonl', 'video_frames.jsonl', 'rider_native_samples.jsonl',
       'trace.jsonl', 'capture/evidence.jsonl', 'body_history.jsonl',
       'capture/native/frames.jsonl', 'road.xodr',
       'capture/recorder_info.txt', 'capture/manifest.json',
       'rider-source-manifest.json', 'authored-sign.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--kind', choices=('mounted_obey', 'mounted_turn', 'dismounted_turn'), default='mounted_turn')
    parser.add_argument('--candidate', choices=('primary', 'fallback1', 'fallback2'), default='primary')
    parser.add_argument('--replace', action='store_true', help='Refresh retained sources after construction changes')
    args = parser.parse_args()
    source = Path(args.source).resolve()
    stem = 'v2-'+args.kind.replace('_', '-')+'-'+args.candidate
    destination = HERE/(stem+'-source')
    destination.mkdir(exist_ok=True)
    items = []
    for name in RAW:
        src, target = source/name, destination/name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if sha(target) != sha(src):
                if not args.replace:
                    raise ValueError('Existing source differs: '+name)
                shutil.copyfile(src, target)
        else:
            shutil.copyfile(src, target)
        if target.stat().st_size > 2*1024*1024:
            raise ValueError('Source exceeds return cap: '+name)
        items.append({'path': name, 'source': str(target.relative_to(ROOT)), 'sha256': sha(target)})
    frames = [json.loads(line) for line in (source/'capture/native/frames.jsonl').read_text().splitlines()]
    if len(frames) != 600:
        raise ValueError('Expected 600 Native frame identities')
    graphs = []
    for frame in frames:
        path = 'capture/native/'+frame['adapter_graph']
        graph = json.loads((source/path).read_text())
        graphs.append({'path': path, 'attributes': graph['metadata'],
                       'nodes': graph['nodes'], 'edges': graph['edges']})
    videos = [{'path': name+'.mkv', 'frames': 600, 'width': width,
               'height': height, 'fps': 20, 'color': color}
              for name, width, height, color in
              (('overview', 1920, 1080, 'blue'),
               ('approach', 1280, 720, 'green'),
               ('reference_corner', 1280, 720, 'white'),
               ('driver_reference', 1280, 720, 'red'))]
    specification = {'files': {}, 'graphs': graphs, 'videos': videos}
    generator = HERE/(stem+'-generator.json')
    generator.write_text(json.dumps(specification, separators=(',', ':'))+'\n')
    if generator.stat().st_size > 2*1024*1024:
        raise ValueError('Generator exceeds return cap')
    recipe = {'format': 'worker-fixture-recipe', 'sources': items,
              'generator': {'source': str(generator.relative_to(ROOT)), 'sha256': sha(generator)}}
    recipe_path = HERE/(stem+'-recipe.json')
    recipe_path.write_text(json.dumps(recipe, indent=2)+'\n')
    print(json.dumps({'source_count': len(items), 'graphs': len(graphs),
                      'videos': len(videos), 'recipe_sha256': sha(recipe_path),
                      'generator_sha256': sha(generator)}))


if __name__ == '__main__':
    main()
