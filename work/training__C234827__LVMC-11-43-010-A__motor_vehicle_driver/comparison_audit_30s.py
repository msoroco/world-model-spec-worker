"""Audit paired selected constructions and synthetic rotation evidence."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(diagnostic):
    if not diagnostic:
        raise ValueError('Original Native paired rotary motion and camera pixels required for comparison acceptance')
    constructions = [json.loads((HERE / f'selected-construction-witness_{i}.json').read_text())
                     for i in (1, 2)]
    files = [{item['path']: item['content'] for item in row['files']}
             for row in constructions]
    if set(files[0]) != set(files[1]) or any(
            files[0][name] != files[1][name] for name in files[0]
            if name not in ('config.json', 'requested-tracks.jsonl')):
        raise ValueError('Paired runner, road, island or analysis source differs')
    configs = [json.loads(item['config.json']) for item in files]
    expected_differences = {'case_id', 'selected_case_id', 'supported_case_ids',
                            'requested_rotation_sign', 'tracks_sha256', 'case'}
    if {key for key in configs[0] if configs[0][key] != configs[1][key]} != expected_differences:
        raise ValueError('Uncontrolled selected configuration difference')
    if [row['requested_rotation_sign'] for row in configs] != [1, -1]:
        raise ValueError('Selected rotation signs differ from pair definition')
    for index, construction in enumerate(constructions, 1):
        source = HERE / 'selected-source' / f'witness_{index}'
        trace = [json.loads(line) for line in (source / 'native-raw-actors.jsonl').read_text().splitlines()]
        if len(trace) != 600 or any(row['candidate_id'] != 'primary' for row in trace):
            raise ValueError('Incomplete selected source pair')
        public = json.loads((HERE / 'selected-proofs' /
                             f'witness_{index}-primary-compatibility.json').read_text())
        saved = json.loads((HERE / 'selected-proofs' /
                            f'witness_{index}-primary-processing.json').read_text())
        if (not public['passed'] or not saved['passed'] or
                public['construction_sha256'] != sha(HERE / f'selected-construction-witness_{index}.json')):
            raise ValueError('Pair lacks current public or saved proof')
    return {'pair': [item['case_id'] for item in constructions],
            'fixed_file_sha256': {name: hashlib.sha256(files[0][name].encode()).hexdigest()
                                  for name in files[0] if name not in ('config.json', 'requested-tracks.jsonl')},
            'requested_rotation_signs': [1, -1], 'synthetic_source_frames': [600, 600],
            'diagnostic_only': True, 'original_native_observed': False,
            'physical_acceptance': False, 'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(args.diagnostic), sort_keys=True))
