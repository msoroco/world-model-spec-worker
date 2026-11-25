"""Create source-shaped synthetic curve traces; no physical claim."""
import hashlib
import json
import math
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def rewrite_rows(path, rows):
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))


def lateral(y):
    station = y + 240
    for begin, finish, start, end in ((0, 100, 0, 0), (100, 145, 0, 1.2),
                                      (145, 190, 1.2, -1.2), (190, 233, -1.2, 0)):
        if station <= finish:
            t = max(0.0, min(1.0, (station - begin) / (finish - begin)))
            return start + (end - start) * (3*t*t - 2*t*t*t)
    return 0.0


def build(old, new):
    target = HERE / 'curve-branch-drafts' / new
    source = target / 'source'
    if source.exists():
        raise ValueError('Refuse to replace curve proof source: ' + str(source))
    shutil.copytree(HERE / f'current-v2-{old}-source', source)
    road = target / 'authored-road.xodr'
    (source / 'road.xodr').write_bytes(road.read_bytes())
    native = [json.loads(line) for line in (source / 'native_samples.jsonl').read_text().splitlines()]
    offsets = [lateral(row['ego_position_m'][1]) for row in native]
    velocities = [(offsets[min(i+1, len(native)-1)] - offsets[max(i-1, 0)]) * 10
                  for i in range(len(native))]
    for row, z, vz in zip(native, offsets, velocities):
        row['ego_position_m'][0] += z
        row['ego_velocity_mps'][0] = vz
        for vertex in row['ego_body_vertices_m']:
            vertex[0] += z
    rewrite_rows(source / 'native_samples.jsonl', native)
    trace = [json.loads(line) for line in (source / 'trace.jsonl').read_text().splitlines()]
    evidence = [json.loads(line) for line in (source / 'capture/evidence.jsonl').read_text().splitlines()]
    bodies = [json.loads(line) for line in (source / 'body_history.jsonl').read_text().splitlines()]
    generator = json.loads((HERE / f'current-v2-{old}-generator.json').read_text())
    for i, (row, ev, body, graph, sample) in enumerate(zip(trace, evidence, bodies, generator['graphs'], native)):
        z = offsets[i]
        row['position']['x'] += z; row['position_m'][0] += z
        row['velocity_mps'][0] = velocities[i]
        speed = math.sqrt(sum(v*v for v in sample['ego_velocity_mps']))
        row['speed_mps'] = speed; row['speed_mph'] = speed / .44704
        ev['ego']['position_m'][0] += z
        ev['ego']['velocity_mps'][0] = velocities[i]
        ev['ego']['speed_mps'] = speed
        for vertex in ev['ego']['body_vertices_m']:
            vertex[0] += z
        for vertex in body['body_vertices_m']:
            vertex[0] += z
        graph['nodes'][0]['attributes']['vertex'][0] += z
        graph['nodes'][0]['attributes']['carla_speed'] = speed
    rewrite_rows(source / 'trace.jsonl', trace)
    rewrite_rows(source / 'capture/evidence.jsonl', evidence)
    rewrite_rows(source / 'body_history.jsonl', bodies)
    context = json.loads((source / 'context.json').read_text())
    context['curve_design'] = {'road_id': 1, 'offset_stations_m': [100, 145, 190, 233],
                               'authored_lateral_excursion_m': 2.4,
                               'source_kind': 'synthetic_cpu_curve_fixture',
                               'physical_curve_review': 'unverified'}
    write(source / 'context.json', context)
    capture = json.loads((source / 'capture/manifest.json').read_text())
    for relative in ('road.xodr', 'native_samples.jsonl', 'trace.jsonl',
                     'capture/evidence.jsonl', 'body_history.jsonl', 'context.json'):
        capture['sources'][relative] = sha(source / relative)
    write(source / 'capture/manifest.json', capture)
    spec = target / 'generator.json';write(spec, generator)
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': p.relative_to(source).as_posix(),
                           'source': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)}
                          for p in sorted(source.rglob('*')) if p.is_file()],
              'generator': {'source': spec.relative_to(ROOT).as_posix(), 'sha256': sha(spec)}}
    write(target / 'recipe.json', recipe)
    manifest = json.loads((HERE / f'current-v2-{old}-diagnostic-manifest.json').read_text())
    entry = manifest['cases'][0]
    entry['case_id'] = HERE.name + '__' + new
    entry['measurement_contract'] = new + '-measurement-contract.json'
    entry['construction'] = f'curve-branch-drafts/{new}/construction.json'
    entry['construction_sha256'] = sha(target / 'construction.json')
    entry['fixture_recipe'] = (target / 'recipe.json').relative_to(ROOT).as_posix()
    entry['kind'] = 'draft_not_selected'
    fallback = HERE / 'curve-branch-drafts' / (new + '-fallback1') / 'construction.json'
    entry['candidates'] = [{'id': 'fallback1',
                            'construction': f'curve-branch-drafts/{new}-fallback1/construction.json',
                            'construction_sha256': sha(fallback)}]
    write(HERE / f'{new}-diagnostic-manifest.json', manifest)
    shutil.copyfile(target / 'measurement-contract.json', HERE / f'{new}-measurement-contract.json')
    return target


if __name__ == '__main__':
    for old, new in (('probe_a', 'curve_probe_a'), ('probe_b', 'curve_probe_b')):
        print(build(old, new))
