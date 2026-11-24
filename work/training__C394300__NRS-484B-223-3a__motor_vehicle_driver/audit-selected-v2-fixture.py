"""Audit explicit diagnostic fixture sources without treating them as Native evidence."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c394300-selected-v2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(case):
    recipe_path = HERE / f'selected-v2-{case}-recipe.json'
    recipe = json.loads(recipe_path.read_text())
    generator_path = ROOT / recipe['generator']['source']
    assert sha(generator_path) == recipe['generator']['sha256']
    generator = json.loads(generator_path.read_text())
    fixture = SCRATCH / f'fixture-{case}'
    assert fixture.is_dir()
    for source in recipe['sources']:
        assert sha(ROOT / source['source']) == source['sha256']
        assert sha(fixture / source['path']) == source['sha256']
    frames = [json.loads(line) for line in
              (fixture / 'capture/native/frames.jsonl').read_text().splitlines()]
    assert len(frames) == len(generator['graphs']) == 480
    for index, frame in enumerate(frames):
        assert frame['frame'] == index
        assert 'base' not in frame and 'abstract' not in frame
        path = fixture / 'capture/native' / frame['adapter_graph']
        assert path.is_file()
        graph = json.loads(path.read_text())
        assert graph['format'] == 'native-adapter-graph-v1'
        assert graph['metadata']['frame'] == index
    videos = {}
    assert {item['path'] for item in generator['videos']} == {
        'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
        'driver_reference.mkv'}
    for video in generator['videos']:
        path = fixture / video['path']
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                                '-select_streams', 'v:0', '-show_entries',
                                'stream=codec_name,width,height,nb_read_frames',
                                '-of', 'json', str(path)], capture_output=True,
                               text=True, check=True)
        stream = json.loads(probe.stdout)['streams'][0]
        assert stream['codec_name'] == 'ffv1'
        assert (stream['width'], stream['height']) == (video['width'], video['height'])
        assert int(stream['nb_read_frames']) == video['frames'] == 480
        videos[video['path']] = {'frames': 480, 'sha256': sha(path)}
    return {'case': case, 'recipe_sha256': sha(recipe_path),
            'generator_sha256': sha(generator_path), 'source_count': len(recipe['sources']),
            'adapter_graphs': len(generator['graphs']), 'videos': videos,
            'scope': 'synthetic diagnostic CPU fixture only; no acquired pixels or legal verdict'}


if __name__ == '__main__':
    report = [audit(case) for case in ('controlled_1', 'controlled_2')]
    path = HERE / 'selected-v2-fixture-audit.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
