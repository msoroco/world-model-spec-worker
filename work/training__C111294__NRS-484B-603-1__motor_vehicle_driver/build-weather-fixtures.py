"""Create source-shaped wet-weather CPU fixtures for separate draft cases."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def build(old, new):
    target = HERE / 'weather-branch-drafts' / new
    source = target / 'source'
    if source.exists():
        shutil.rmtree(source)
    shutil.copytree(HERE / f'current-v2-{old}-source', source)
    context = json.loads((source / 'context.json').read_text())
    context['weather_parameters'] = {'preset': 'WetCloudyNoon', 'precipitation': 0.0,
                                     'wetness': 90.0, 'source_kind': 'synthetic_cpu_weather_fixture'}
    write(source / 'context.json', context)
    evidence = source / 'capture/evidence.jsonl'
    updated = []
    for line in evidence.read_text().splitlines():
        row = json.loads(line)
        row['world']['weather'] = {'cloudiness': 80.0, 'precipitation': 0.0,
                                   'wetness': 90.0, 'fog_density': 0.0}
        updated.append(json.dumps(row))
    evidence.write_text('\n'.join(updated) + '\n')
    capture = json.loads((source / 'capture/manifest.json').read_text())
    capture['sources']['context.json'] = sha(source / 'context.json')
    capture['sources']['capture/evidence.jsonl'] = sha(evidence)
    write(source / 'capture/manifest.json', capture)
    generator = target / 'generator.json'
    shutil.copyfile(HERE / f'current-v2-{old}-generator.json', generator)
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': p.relative_to(source).as_posix(),
                           'source': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)}
                          for p in sorted(source.rglob('*')) if p.is_file()],
              'generator': {'source': generator.relative_to(ROOT).as_posix(),
                            'sha256': sha(generator)}}
    write(target / 'recipe.json', recipe)
    manifest = json.loads((HERE / f'current-v2-{old}-diagnostic-manifest.json').read_text())
    entry = manifest['cases'][0]
    entry['case_id'] = HERE.name + '__' + new
    entry['construction'] = 'construction.json'
    entry['construction_sha256'] = sha(target / 'construction.json')
    entry['fixture_recipe'] = (target / 'recipe.json').relative_to(ROOT).as_posix()
    entry['kind'] = 'draft_not_selected'
    entry['candidates'] = []
    write(target / 'manifest.json', manifest)
    return target


if __name__ == '__main__':
    for old, new in (('probe_a', 'weather_probe_a'), ('probe_b', 'weather_probe_b')):
        print(build(old, new))
