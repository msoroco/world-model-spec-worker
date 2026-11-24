"""Independent source-joined body-footprint check for selected CPU fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from body_footprint import measure_evidence_body


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def audit(attempts):
    measured = []
    for number in (1, 2):
        attempt = attempts[number]
        recipe = read(HERE / f'v2-probe{number}-fixture-recipe.json')
        source_hashes = {s['path']: s['sha256'] for s in recipe['sources']}
        for name in ('actor-poses.jsonl', 'capture/evidence.jsonl', 'crossing-context.json'):
            if sha(attempt / name) != source_hashes[name]:
                raise ValueError(f'Probe {number} original body source changed: {name}')
        result = measure_evidence_body(lines(attempt / 'actor-poses.jsonl'),
                                       lines(attempt / 'capture/evidence.jsonl'),
                                       read(attempt / 'crossing-context.json'))
        measured.append(result)
    if [m['roadway_body_frames_not_wholly_inside_one_crosswalk'] for m in measured] != [17, 129]:
        raise ValueError('Diagnostic body-footprint difference changed')
    if [m['roadway_point_frames_outside_crosswalk'] for m in measured] != [0, 121]:
        raise ValueError('Diagnostic point-path difference changed')
    return {'format': 'c188094-selected-body-source-cpu-audit', 'passed': True,
            'body_meter_sha256': sha(HERE / 'native/body_footprint.py'),
            'attempt_source_hashes': [
                {name: sha(attempts[number] / name) for name in
                 ('actor-poses.jsonl', 'capture/evidence.jsonl', 'crossing-context.json')}
                for number in (1, 2)],
            'body_outside_frames': [17, 129], 'point_outside_frames': [0, 121],
            'roadway_occupancy_rule': 'original body polygon intersects roadway, including when center is outside',
            'diagnostic_only': True, 'original_native_physical_observed': False,
            'business_district_confirmed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt1', type=Path, required=True)
    parser.add_argument('--attempt2', type=Path, required=True)
    args = parser.parse_args()
    result = audit({1: args.attempt1, 2: args.attempt2})
    (HERE / 'v2-selected-body-independent-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
