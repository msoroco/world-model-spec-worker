"""Independent CPU comparison of selected source-shaped crosswalk pairs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from measure_crosswalk import measure

HERE = Path(__file__).resolve().parent
FIELD = {'exception_1': 'traffic_conflict', 'exception_2': 'law_compliance',
         'exception_3': 'officer_direction', 'exception_4': 'device_direction'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def inspect(comparison, source_root=HERE / 'selected-source'):
    case_a, case_b = comparison['case_ids']
    suffix_a, suffix_b = (case.rsplit('__', 1)[-1] for case in (case_a, case_b))
    if suffix_a.rsplit('_', 1)[0] != suffix_b.rsplit('_', 1)[0]:
        raise ValueError('Comparison branch differs')
    branch = suffix_a.rsplit('_', 1)[0]
    folder_a, folder_b = source_root / suffix_a, source_root / suffix_b
    map_a, map_b = folder_a / 'road.xodr', folder_b / 'road.xodr'
    if not map_a.is_file() or not map_b.is_file() or sha(map_a) != sha(map_b):
        raise ValueError('Fixed crosswalk map source differs')
    config_a = load(HERE / 'native/bundles' / suffix_a / 'construction.json')
    config_b = load(HERE / 'native/bundles' / suffix_b / 'construction.json')
    cfg_a = json.loads(next(item['content'] for item in config_a['files']
                            if item['path'] == 'config.json'))
    cfg_b = json.loads(next(item['content'] for item in config_b['files']
                            if item['path'] == 'config.json'))
    for key in ('assignment_id', 'law_id', 'cell_id', 'actor', 'frozen_cell',
                'rate_hz', 'frames', 'duration_s', 'source_cameras'):
        if cfg_a[key] != cfg_b[key]:
            raise ValueError('Fixed selected construction changed: ' + key)
    if sha(HERE / ('selected-generator-witness_1.json')) != load(
            HERE / ('selected-recipe-' + suffix_a + '.json'))['generator']['sha256']:
        raise ValueError('First diagnostic video policy changed')
    if sha(HERE / ('selected-generator-witness_1.json')) != load(
            HERE / ('selected-recipe-' + suffix_b + '.json'))['generator']['sha256']:
        raise ValueError('Second diagnostic video policy changed')
    measured_a = measure(folder_a, case_a)
    measured_b = measure(folder_b, case_b)
    context_a = load(folder_a / 'exception-context.json')['context']
    context_b = load(folder_b / 'exception-context.json')['context']
    if context_a['activity'] != context_b['activity']:
        raise ValueError('Fixed stop/stand/park activity changed')
    if branch.startswith('exception_'):
        field = FIELD[branch]
        if measured_a['crosswalk_occupied_while_at_rest_frames'] != measured_b['crosswalk_occupied_while_at_rest_frames']:
            raise ValueError('Fixed crosswalk occupancy changed')
        if context_a[field] is not False or context_b[field] is not True:
            raise ValueError('Exact cited exception source did not change')
        for other in FIELD.values():
            if other != field and (context_a[other] is not False or context_b[other] is not False):
                raise ValueError('Non-target exception source changed')
        changed = field
    else:
        if measured_a['crosswalk_occupied_while_at_rest_frames'] != 0 or measured_b['crosswalk_occupied_while_at_rest_frames'] <= 0:
            raise ValueError('Crosswalk occupancy contrast absent')
        if context_a != context_b:
            raise ValueError('Fixed exception context changed')
        changed = 'crosswalk_occupancy'
    return {'format': 'c229397-crosswalk-comparison-cpu-v1',
        'comparison_id': comparison['comparison_id'], 'case_ids': [case_a, case_b],
        'passed': True, 'fixed_conditions_checked': ['crosswalk_map_hash',
            'actor_and_frozen_cell', 'capture_policy', 'stop_stand_park_activity',
            'non_target_exception_sources'],
        'deliberate_difference_observed': changed,
        'source_sha256': {suffix: {name: sha(folder / name) for name in
            ('road.xodr', 'actor-sources.jsonl', 'crosswalk-source.json',
             'exception-context.json')}
            for suffix, folder in ((suffix_a, folder_a), (suffix_b, folder_b))},
        'diagnostic_only': True, 'original_native_observed': False,
        'legal_verdict': None}


def build():
    plan = load(HERE / 'case-plan.json')
    for comparison in plan['comparisons']:
        proof = inspect(comparison)
        path = HERE / 'comparison-proof' / (comparison['comparison_id'].rsplit('__', 1)[-1] + '.json')
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(proof, indent=2) + '\n')
        print(comparison['comparison_id'].rsplit('__', 1)[-1])


def negative():
    plan = load(HERE / 'case-plan.json')
    scratch = Path(os.environ['TMPDIR']).resolve()
    if '.runtime-work' not in scratch.parts:
        raise ValueError('Comparison scratch must stay under .runtime-work')
    with tempfile.TemporaryDirectory(dir=scratch, prefix='comparison-negative-') as temporary:
        root = Path(temporary)
        for comparison in plan['comparisons']:
            names = [case.rsplit('__', 1)[-1] for case in comparison['case_ids']]
            for name in names:
                shutil.copytree(HERE / 'selected-source' / name, root / name)
            (root / names[0] / 'road.xodr').unlink()
            try:
                inspect(comparison, root)
            except ValueError as error:
                if 'Fixed crosswalk map source differs' not in str(error):
                    raise
            else:
                raise AssertionError('Comparison accepted missing crosswalk map')
            for name in names:
                shutil.rmtree(root / name)
            print(comparison['comparison_id'].rsplit('__', 1)[-1] + ': missing source rejected')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    if args.build:
        build()
    elif args.negative:
        negative()
    else:
        parser.error('Use --build')
