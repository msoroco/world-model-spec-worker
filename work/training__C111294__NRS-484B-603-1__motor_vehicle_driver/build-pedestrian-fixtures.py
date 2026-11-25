"""Create source-shaped pedestrian CPU fixtures without claiming Native acquisition."""
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
    target = HERE / 'pedestrian-branch-drafts' / new
    source = target / 'source'
    if source.exists():
        shutil.rmtree(source)
    shutil.copytree(HERE / f'current-v2-{old}-source', source)
    samples = source / 'native_samples.jsonl'
    updated = []
    for line in samples.read_text().splitlines():
        row = json.loads(line)
        row.update(pedestrian_actor_id=303, pedestrian_role='pedestrian',
                   pedestrian_blueprint='walker.pedestrian.synthetic',
                   pedestrian_position_m=[-10.0 + row['frame'] / 20.0, -5.0, 0.5])
        updated.append(json.dumps(row))
    samples.write_text('\n'.join(updated) + '\n')
    context = json.loads((source / 'context.json').read_text())
    context['pedestrian_hazard'] = {
        'route': 'walk from x=-10 toward crossing at y=-5',
        'source_kind': 'synthetic_cpu_pedestrian_fixture',
        'pedestrian_actor_id': 303,
        'physical_conflict_review': 'unverified'}
    write(source / 'context.json', context)
    evidence = source / 'capture/evidence.jsonl'
    updated = []
    for line in evidence.read_text().splitlines():
        row = json.loads(line)
        row['world']['pedestrian'] = {
            'actor_id': 303,
            'position_m': [-10.0 + (row['original_frame'] - 100) / 20.0, -5.0, 0.5],
            'source_kind': 'synthetic_cpu_pedestrian_fixture'}
        updated.append(json.dumps(row))
    evidence.write_text('\n'.join(updated) + '\n')
    capture = json.loads((source / 'capture/manifest.json').read_text())
    for relative in ('native_samples.jsonl', 'context.json', 'capture/evidence.jsonl'):
        capture['sources'][relative] = sha(source / relative)
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
    selected = json.loads((HERE / f'weather_{old}-diagnostic-manifest.json').read_text())
    chosen = selected['cases'][0]
    chosen['case_id'] = HERE.name + '__' + new
    chosen['measurement_contract'] = new + '-measurement-contract.json'
    chosen['construction'] = f'pedestrian-branch-drafts/{new}/construction.json'
    chosen['construction_sha256'] = sha(target / 'construction.json')
    chosen['fixture_recipe'] = (target / 'recipe.json').relative_to(ROOT).as_posix()
    fallback = HERE / 'pedestrian-branch-drafts' / (new + '-fallback1') / 'construction.json'
    chosen['candidates'] = [{
        'id': 'fallback1',
        'construction': f'pedestrian-branch-drafts/{new}-fallback1/construction.json',
        'construction_sha256': sha(fallback)}]
    write(HERE / f'{new}-diagnostic-manifest.json', selected)
    shutil.copyfile(target / 'measurement-contract.json', HERE / f'{new}-measurement-contract.json')
    return target


if __name__ == '__main__':
    for old, new in (('probe_a', 'pedestrian_probe_a'), ('probe_b', 'pedestrian_probe_b')):
        print(build(old, new))
