"""Exercise paired 600-frame saved-source diagnostics without CARLA."""
from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import hashlib
import json
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIXTURES = ROOT / '.runtime-work' / 'c111294-yield-source-proof'
SPEC = spec_from_file_location('measure_yield', HERE / 'native' / 'measure_yield.py')
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def entrant_position(index):
    if index < 140:
        return -12.0
    if index < 180:
        return -12.0 + (index - 140) / 8.0
    if index < 260:
        return -7.0 + (index - 180) * 14.0 / 80.0
    return 7.0 + (index - 260) / 5.0


def through_position(index, yield_case):
    if index < 142:
        return 50.0 - index * .28
    if yield_case and index < 300:
        return 10.24
    release = 300 if yield_case else 142
    return 10.24 - (index - release) * .4


def rows(yield_case):
    result = []
    for index in range(600):
        x = entrant_position(index)
        y = through_position(index, yield_case)
        entrant_speed = 0 if index < 140 else (2.5 if index < 180 else (3.5 if index < 260 else 4))
        through_speed = 5.6 if index < 142 else (0 if yield_case and index < 300 else 8)
        result.append({'video_frame': index, 'native_frame': 100 + index,
                       'time_s': index / 20, 'source_kind': 'synthetic_native_sample',
                       'through': {'x_m': -1.75, 'y_m': y, 'speed_mps': through_speed,
                                   'road_id': 4 if y > 7 else (13 if y >= -7 else 1), 'lane_id': 1},
                       'entrant': {'x_m': x, 'y_m': -1.75, 'speed_mps': entrant_speed,
                                   'road_id': 3 if x < -7 else (14 if x <= 7 else 2), 'lane_id': -1}})
    return result


def write_fixture(root, case, samples):
    root.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HERE / 'native' / 'road.xodr', root / 'road.xodr')
    (root / 'native_samples.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in samples))
    manifest = {'case_id': case, 'source_kind': 'synthetic_native_sample',
                'sha256': {name: sha(root / name) for name in ('road.xodr', 'native_samples.jsonl')}}
    (root / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


def reject(label, root, case, expected):
    try:
        MODULE.measure(root, case)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(f'{label}: wrong rejection: {error}') from error
        return {'label': label, 'expected': expected, 'actual': str(error)}
    raise AssertionError(f'{label}: invalid source passed')


def main():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    case1, case2 = (HERE.name + '__probe_1', HERE.name + '__probe_2')
    source1, source2 = rows(True), rows(False)
    one, two = FIXTURES / 'yield', FIXTURES / 'no-yield'
    write_fixture(one, case1, source1)
    write_fixture(two, case2, source2)
    positive = [MODULE.measure(one, case1), MODULE.measure(two, case2)]
    assert positive[0]['through_yield_response_observed'] is True
    assert positive[1]['through_yield_response_observed'] is False
    assert source1[0]['entrant'] == source2[0]['entrant']
    assert all(a['entrant'] == b['entrant'] for a, b in zip(source1, source2))
    assert all(a['through'] == b['through'] for a, b in zip(source1[:142], source2[:142]))
    negatives = []
    negatives.append(reject('wrong-case', one, case2, 'identity differs'))
    damaged = FIXTURES / 'missing-samples'
    write_fixture(damaged, case1, source1)
    (damaged / 'native_samples.jsonl').unlink()
    negatives.append(reject('missing-samples', damaged, case1, 'Missing required source'))
    damaged = FIXTURES / 'altered-unbound-source'
    write_fixture(damaged, case1, source1)
    with (damaged / 'native_samples.jsonl').open('a') as handle:
        handle.write('{}\n')
    negatives.append(reject('unbound-mutation', damaged, case1, 'Saved source hash differs'))
    damaged = FIXTURES / 'short-rebound-source'
    write_fixture(damaged, case1, source1[:-1])
    negatives.append(reject('short-source', damaged, case1, 'Full 600-frame source window absent'))
    damaged = FIXTURES / 'wrong-frame-join'
    invalid = deepcopy(source1)
    invalid[170]['native_frame'] = 999
    write_fixture(damaged, case1, invalid)
    negatives.append(reject('wrong-frame', damaged, case1, 'Original frame join differs'))
    damaged = FIXTURES / 'wrong-road-role'
    invalid = deepcopy(source1)
    invalid[190]['entrant']['road_id'] = 1
    write_fixture(damaged, case1, invalid)
    negatives.append(reject('wrong-road', damaged, case1, 'Native road/lane roles differ'))
    proof = {'format': 'c111294-paired-source-proof-v1', 'assignment_id': HERE.name,
             'source_kind': 'synthetic_native_sample', 'physical_observation_claimed': False,
             'legal_verdict': None, 'positive': positive, 'negatives': negatives,
             'fixed_entrant_full_600_frames': True, 'fixed_through_before_intervention_frames': 142,
             'deliberate_difference': 'through vehicle hold versus continued approach after entrant prior stop',
             'source_measurement_code_sha256': sha(HERE / 'native' / 'measure_yield.py'),
             'source_construction_code_sha256': sha(Path(__file__))}
    output = HERE / 'yield-sequence-proof.json'
    output.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed': True, 'proof_sha256': sha(output),
                      'positive_count': len(positive), 'negative_count': len(negatives)}, sort_keys=True))


if __name__ == '__main__':
    main()
