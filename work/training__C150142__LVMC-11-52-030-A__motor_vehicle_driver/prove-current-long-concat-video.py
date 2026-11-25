"""Prove a source-hashed text playlist can supply full-length synthetic cameras."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT',
                      str(REPO / '.runtime-work' / 'owner150142' / 'concat-proof'))
sys.path.insert(0, str(REPO / 'runtime' / 'scenario_pipeline'))
from worker_exchange.fixture_recipe import inspect
from worker_exchange.media import check_four_view_sources


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


recipe_path = HERE / 'current-tour-bus-below-concat-video-recipe.json'
recipe, sources = inspect(REPO, recipe_path)
fixture = REPO / '.runtime-work' / 'owner150142' / 'concat-fixture-tour-bus-below-v3'
views = ('overview', 'approach', 'reference_corner', 'driver_reference')
for view in views:
    path = fixture / (view + '.mkv')
    assert path.read_bytes().startswith(b'ffconcat version 1.0\n')
    assert sha(path) == sha(sources[view + '.mkv'])
check_four_view_sources({view: fixture / (view + '.mkv') for view in views})
probe = json.loads(subprocess.check_output([
    'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
    '-show_entries', 'stream=width,height,r_frame_rate,nb_read_frames',
    '-of', 'json', str(fixture / 'overview.mkv')], text=True))['streams'][0]
assert probe['r_frame_rate'] == '20/1' and int(probe['nb_read_frames']) == 36120
assert [probe['width'], probe['height']] == [1920, 1080]
frame_map = fixture / 'video_frames.jsonl'
assert sum(1 for _ in frame_map.open()) == 36120
assert sha(frame_map) == sha(sources['video_frames.jsonl'])
proof = {'format': 'c150142-long-concat-video-proof-v1',
         'passed': True, 'case_id': HERE.name + '__tour_bus_below',
         'recipe_sha256': sha(recipe_path), 'frame_map_sha256': sha(frame_map),
         'overview_decode': probe, 'all_four_camera_preflight': True,
         'source_hashes': {path: sha(source) for path, source in sources.items()},
         'original_native_observed': False,
         'official_compatibility_claimed': False}
path = HERE / 'current-long-concat-video-proof.json'
path.write_text(json.dumps(proof, indent=2) + '\n')
print(json.dumps({'proof_sha256': sha(path), 'frames': 36120}, sort_keys=True))
