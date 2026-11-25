"""Compare selected source-shaped approach and traversal intervals independently."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = {'probe_01': 'primary', 'probe_02': 'contrast', 'probe_03': 'traversal'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(diagnostic):
    if not diagnostic:
        raise ValueError('Original physical highway and paired Native body passage required for comparison acceptance')
    fixed = ('road.xodr', 'runner.py', 'selected_capture.py', 'finalize.py', 'zone_measure.py')
    hashes = {}
    intervals = {}
    cases = []
    for suffix in NAME:
        construction = json.loads((HERE / f'selected-construction-{suffix}.json').read_text())
        files = {item['path']: item['content'] for item in construction['files']}
        for name in fixed:
            value = hashlib.sha256(files[name].encode()).hexdigest()
            if name in hashes and hashes[name] != value:
                raise ValueError('Selected fixed implementation/road differs: ' + name)
            hashes[name] = value
        config = json.loads(files['config.json'])
        intervals[suffix] = config['requested_left_interval']
        cases.append(construction['case_id'])
        public_path = HERE / 'selected-proofs' / f'{suffix}-primary-compatibility.json'
        saved_path = HERE / 'selected-proofs' / f'{suffix}-primary-processing.json'
        public = json.loads(public_path.read_text())
        saved = json.loads(saved_path.read_text())
        if (not public['passed'] or not saved['passed'] or
                public['construction_sha256'] != sha(HERE / f'selected-construction-{suffix}.json')):
            raise ValueError('Selected source pair lacks final public/saved proof')
        source = HERE / f'current-v2-{NAME[suffix]}-sources'
        body = (source / 'vehicle-footprints.jsonl').read_text().splitlines()
        if len(body) != 600:
            raise ValueError('Incomplete selected diagnostic body source')
        measured = public['measurement_examples']['zone_measurement']['value']
        expected = {'probe_01': (None, None), 'probe_02': (240, 358),
                    'probe_03': (None, 400)}[suffix]
        if (measured['first_left_approach_frame'], measured['first_left_traversal_frame']) != expected:
            raise ValueError('Selected source interval differs from exact comparison')
    if intervals != {'probe_01': [], 'probe_02': [240, 359], 'probe_03': [400, 450]}:
        raise ValueError('Selected requested intervals differ')
    return {'case_ids': cases, 'fixed_file_sha256': hashes,
            'requested_left_intervals': intervals, 'diagnostic_frames': 600,
            'original_native_observed': False, 'physical_acceptance': False,
            'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(args.diagnostic), sort_keys=True))
