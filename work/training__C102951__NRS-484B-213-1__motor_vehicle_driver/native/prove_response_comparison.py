"""Controlled synthetic 2x2 actor-response comparison at the 170 m probe."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from measure_response import measure_response

HERE = Path(__file__).resolve().parent
ACTORS = ('oncoming', 'overtaken')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write(path, data):
    path.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in data))


def make_variants():
    baseline = HERE/'saved-fixtures'/'170'
    combined = HERE/'response-fixtures'/'reaction-170'
    base_rows = rows(baseline/'native-observed.jsonl')
    both_rows = rows(combined/'native-observed.jsonl')
    paths = {'none': baseline, 'both': combined}
    for actor in ACTORS:
        folder = HERE/'response-fixtures'/('only-'+actor+'-170')
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(baseline/'road-readback.json', folder/'road-readback.json')
        altered = [dict(row) for row in base_rows]
        for row, changed in zip(altered, both_rows):
            for suffix in ('speed_mps', 'x_m'):
                key = actor+'_'+suffix
                row[key] = changed[key]
        write(folder/'native-observed.jsonl', altered)
        paths[actor] = folder
    return paths


def compare(paths):
    datasets = {name: rows(folder/'native-observed.jsonl') for name, folder in paths.items()}
    if set(datasets) != {'none', 'oncoming', 'overtaken', 'both'} or any(len(data) != 480 for data in datasets.values()):
        raise ValueError('Response factorial coverage differs')
    road_hashes = {sha(folder/'road-readback.json') for folder in paths.values()}
    if len(road_hashes) != 1:
        raise ValueError('Response factorial road differs')
    for i in range(480):
        base = datasets['none'][i]
        for variant, data in datasets.items():
            row = data[i]
            fixed = set(base) - {actor+'_'+suffix for actor in ACTORS for suffix in ('speed_mps', 'x_m')}
            if any(row[key] != base[key] for key in fixed):
                raise ValueError('Response factorial fixed context differs')
            for actor in ACTORS:
                source = datasets['both'][i] if actor in variant or variant == 'both' else base
                if any(row[actor+'_'+suffix] != source[actor+'_'+suffix] for suffix in ('speed_mps', 'x_m')):
                    raise ValueError('Response factorial actor intervention differs')
    measured = {name: measure_response(folder) for name, folder in paths.items()}
    if len({value['pass_entry_frame'] for value in measured.values()}) != 1 or len({value['pass_return_frame'] for value in measured.values()}) != 1:
        raise ValueError('Response factorial pass window differs')
    drops = {name: {actor: result['response'][actor]['maximum_left_phase_speed_drop_mps']
                    for actor in ACTORS} for name, result in measured.items()}
    if drops != {'none': {'oncoming': 0, 'overtaken': 0},
                 'oncoming': {'oncoming': 4, 'overtaken': 0},
                 'overtaken': {'oncoming': 0, 'overtaken': 4},
                 'both': {'oncoming': 4, 'overtaken': 4}}:
        raise ValueError('Response factorial measured contrast differs')
    return measured, drops


def prove():
    paths = make_variants()
    measured, drops = compare(paths)
    negatives = []
    for mutation in ('ego_trajectory', 'sightline', 'unrequested_actor', 'road_readback'):
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            changed = Path(temporary)/'changed'
            shutil.copytree(paths['oncoming'], changed)
            if mutation == 'road_readback':
                (changed/'road-readback.json').write_bytes((changed/'road-readback.json').read_bytes()+b' ')
            else:
                data = rows(changed/'native-observed.jsonl')
                if mutation == 'ego_trajectory': data[60]['ego_x_m'] += 1
                elif mutation == 'sightline': data[60]['sightline_visible'] = False
                else: data[60]['overtaken_speed_mps'] += 1
                write(changed/'native-observed.jsonl', data)
            altered = dict(paths, oncoming=changed)
            try:
                compare(altered)
            except ValueError:
                negatives.append({'mutation': mutation, 'rejected': True})
            else:
                raise AssertionError('Changed factorial control accepted: '+mutation)
    proof = {'format': 'c102951-controlled-response-factorial-v1',
             'assignment_id': HERE.parent.name,
             'processor_sha256': sha(HERE/'measure_response.py'),
             'sources': {name: {file: sha(folder/file) for file in ('native-observed.jsonl','road-readback.json')}
                         for name, folder in paths.items()},
             'pass_window': [measured['none']['pass_entry_frame'], measured['none']['pass_return_frame']],
             'speed_drop_mps': drops, 'negatives': negatives,
             'original_native_observed': False, 'accepted_comparison': False,
             'causal_judgment': None, 'interference_judgment': None,
             'delivery_ready': False}
    (HERE/'response-comparison-proof.json').write_text(json.dumps(proof, indent=2)+'\n')
    return proof


if __name__ == '__main__':
    print(json.dumps({'variants': len(prove()['sources']), 'negative_controls': 4}))
