"""Construct textual obstruction diagnostics with explicit synthetic provenance."""
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
    target = HERE / 'obstruction-branch-drafts' / new
    source = target / 'source'
    if not source.exists():
        shutil.copytree(HERE / f'current-v2-{old}-source', source)
        samples = source / 'native_samples.jsonl'
        updated = []
        for line in samples.read_text().splitlines():
            row = json.loads(line)
            row.update(obstruction_actor_id=303,
                       obstruction_blueprint='static.prop.streetbarrier',
                       obstruction_position_m=[3.25, -5.0, 0.25])
            updated.append(json.dumps(row))
        samples.write_text('\n'.join(updated) + '\n')
        context = json.loads((source / 'context.json').read_text())
        context['highway_obstruction'] = {
            'kind': 'static roadwork barrier', 'spawn_native_xy_m': [3.25, -5.0],
            'source_kind': 'synthetic_cpu_obstruction_fixture',
            'obstruction_actor_id': 303, 'physical_highway_review': 'unverified'}
        write(source / 'context.json', context)
        evidence = source / 'capture/evidence.jsonl'
        updated = []
        for line in evidence.read_text().splitlines():
            row = json.loads(line)
            row['world']['highway_obstruction'] = {
                'actor_id': 303, 'position_m': [3.25, -5.0, 0.25],
                'blueprint': 'static.prop.streetbarrier',
                'source_kind': 'synthetic_cpu_obstruction_fixture'}
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
    chosen['construction'] = f'obstruction-branch-drafts/{new}/construction.json'
    chosen['construction_sha256'] = sha(target / 'construction.json')
    chosen['fixture_recipe'] = (target / 'recipe.json').relative_to(ROOT).as_posix()
    fallback = HERE / 'obstruction-branch-drafts' / (new + '-fallback1') / 'construction.json'
    chosen['candidates'] = [{
        'id': 'fallback1',
        'construction': f'obstruction-branch-drafts/{new}-fallback1/construction.json',
        'construction_sha256': sha(fallback)}]
    write(HERE / f'{new}-diagnostic-manifest.json', selected)
    shutil.copyfile(target / 'measurement-contract.json', HERE / f'{new}-measurement-contract.json')
    return target


if __name__ == '__main__':
    for old, new in (('probe_a', 'obstruction_probe_a'), ('probe_b', 'obstruction_probe_b')):
        print(build(old, new))
