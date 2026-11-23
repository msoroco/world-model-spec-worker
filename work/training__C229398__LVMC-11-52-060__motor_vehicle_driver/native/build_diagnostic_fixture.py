"""Build the source-inventoried 15-foot diagnostic fixture and recipe."""
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from prove_finalize_saved import fixture

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[1]
SUFFIX = 'at_15_ft'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def build():
    manifest_path = PACKAGE / 'draft-primary-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'].endswith('__' + SUFFIX))
    construction = json.loads((PACKAGE / entry['construction']).read_text())
    source_dir = PACKAGE / 'diagnostic-fixture' / SUFFIX / 'sources'
    source_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work') as temporary:
        attempt = Path(temporary) / 'attempt'
        fixture(attempt, construction, 15)
        names = ('acquisition-provenance.json', 'native-curb-proposal.json',
                 'reviewed-curb.json', 'native-raw-actors.jsonl', 'trace.jsonl',
                 'video_frames.jsonl')
        sources = []
        for name in names:
            destination = source_dir / name
            shutil.copyfile(attempt / name, destination)
            sources.append({'path': name, 'source': str(destination.relative_to(ROOT)),
                            'sha256': sha(destination)})
    videos = []
    for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        videos.append({'path': name + '.mkv', 'frames': 600,
                       'width': 1920 if name == 'overview' else 1280,
                       'height': 1080 if name == 'overview' else 720,
                       'fps': 20, 'color': 'black'})
    spec_path = source_dir.parent / 'diagnostic-generator.json'
    write(spec_path, {'files': {}, 'graphs': [], 'videos': videos})
    recipe_path = source_dir.parent / 'fixture-recipe.json'
    write(recipe_path, {'format': 'worker-fixture-recipe', 'sources': sources,
                        'generator': {'source': str(spec_path.relative_to(ROOT)),
                                      'sha256': sha(spec_path)}})
    entry['fixture_recipe'] = str(recipe_path.relative_to(ROOT))
    write(manifest_path, manifest)
    proposals = PACKAGE / 'proposals/cases.json'
    if not proposals.is_file():
        plan = json.loads((PACKAGE / 'case-plan.json').read_text())
        write(proposals, {'cell_id': plan['cell_id'], 'actor': plan['actor'],
                          'status': 'draft_diagnostic', 'cases': plan['cases']})
    print(json.dumps({'case_id': entry['case_id'], 'source_count': len(sources),
                      'recipe_sha256': sha(recipe_path)}))


if __name__ == '__main__':
    build()
