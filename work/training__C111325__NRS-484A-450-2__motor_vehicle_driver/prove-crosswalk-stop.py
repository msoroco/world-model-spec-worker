"""Controlled source-only fixture for the near-side crosswalk measurement."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / '.runtime-work/c111325-crosswalk-source-proof'
spec = importlib.util.spec_from_file_location('measure_stop', HERE / 'native/measure_stop.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def center(index, stopped):
    if stopped:
        if index < 120:
            return -35 + 21 * index / 120
        if index < 180:
            return -14
        return min(20, -14 + 34 * (index - 180) / 220)
    return min(20, -35 + 55 * index / 400)


def rows(stopped):
    out = []
    for index in range(600):
        y = center(index, stopped)
        prior = center(max(index - 1, 0), stopped)
        vertices = [[x, y + dy, z] for x in (.65, 2.85)
                    for dy in (-2.5, 2.5) for z in (0, 1.5)]
        out.append({'video_frame': index, 'native_frame': 100 + index,
                    'time_s': index / 20, 'source_kind': 'synthetic_native_sample',
                    'road_id': 1 if y < -7 else 13 if y <= 7 else 4,
                    'lane_id': -1, 'speed_mps': abs(y - prior) * 20,
                    'body_vertices_m': vertices})
    return out


def write_fixture(path, case, source_rows):
    path.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HERE / 'native/road.xodr', path / 'road.xodr')
    (path / 'native_samples.jsonl').write_text(
        ''.join(json.dumps(row, sort_keys=True) + '\n' for row in source_rows))
    manifest = {'case_id': case, 'source_kind': 'synthetic_native_sample',
                'sha256': {n: sha(path / n) for n in ('road.xodr', 'native_samples.jsonl')}}
    (path / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


def rejection(path, case, message):
    try:
        module.measure(path, case)
    except ValueError as exc:
        return {'rejected': True, 'reason': str(exc), 'test': message}
    raise AssertionError('Invalid source accepted: ' + message)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cases = {i: HERE.name + f'__probe_{i}' for i in (1, 2)}
    samples = {1: rows(True), 2: rows(False)}
    positives = {}
    for index in (1, 2):
        path = OUT / f'probe-{index}'
        write_fixture(path, cases[index], samples[index])
        positives[str(index)] = module.measure(path, cases[index])
    assert positives['1']['pre_crosswalk_full_halt_observed'] is True
    assert positives['2']['pre_crosswalk_full_halt_observed'] is False
    negatives = []
    base = OUT / 'probe-1'
    negatives.append(rejection(base, cases[2], 'wrong case identity'))
    for name, mutation in (
            ('short-window', lambda r: r.pop()),
            ('wrong-frame', lambda r: r[15].update(native_frame=999)),
            ('wrong-lane', lambda r: r[15].update(lane_id=1)),
            ('no-crossing', lambda r: [row.update(body_vertices_m=[
                [v[0], min(v[1], -12), v[2]] for v in row['body_vertices_m']]) for row in r])):
        altered = copy.deepcopy(samples[1])
        mutation(altered)
        path = OUT / name
        write_fixture(path, cases[1], altered)
        negatives.append(rejection(path, cases[1], name))
    hash_path = OUT / 'changed-hash'
    write_fixture(hash_path, cases[1], samples[1])
    with (hash_path / 'native_samples.jsonl').open('a') as stream:
        stream.write('{}\n')
    negatives.append(rejection(hash_path, cases[1], 'changed source hash'))
    geometry = OUT / 'missing-sign'
    write_fixture(geometry, cases[1], samples[1])
    source = (geometry / 'road.xodr').read_text().replace('name="STOP"', 'name="YIELD"')
    (geometry / 'road.xodr').write_text(source)
    manifest = json.loads((geometry / 'source-manifest.json').read_text())
    manifest['sha256']['road.xodr'] = sha(geometry / 'road.xodr')
    (geometry / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    negatives.append(rejection(geometry, cases[1], 'missing governing sign'))
    report = {'format': 'c111325-crosswalk-source-proof-v1',
              'source_kind': 'synthetic_native_sample',
              'physical_observation_claimed': False, 'legal_verdict': None,
              'controlled_variable': 'requested_stop_before_near_side_crosswalk',
              'positive_measurements': positives, 'negative_rejections': negatives,
              'construction_manifest_sha256': sha(HERE / 'draft-manifest.json')}
    path = HERE / 'crosswalk-source-proof.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'proof_sha256': sha(path), 'positives': len(positives),
                      'negatives': len(negatives)}, sort_keys=True))


if __name__ == '__main__':
    main()
