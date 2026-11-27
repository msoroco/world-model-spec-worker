"""CPU proof for prospective same-cell roadway-entry request isolation."""

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from check_entry_return import check
from build_entry_return import POLICIES, ROOT


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rejected(fn, expected):
    try:
        fn()
    except ValueError as error:
        if expected not in str(error):
            raise
        return str(error)
    raise AssertionError('Changed source was accepted: ' + expected)


def run():
    scratch = Path(os.environ.get('TMPDIR', '.runtime-work')).resolve()
    if scratch.name != '.runtime-work' and '.runtime-work' not in scratch.parts:
        raise ValueError('Temporary entry-return proof must stay under .runtime-work')
    scratch.mkdir(parents=True, exist_ok=True)
    positive = check()
    negatives = []
    with tempfile.TemporaryDirectory(prefix='c213851-entry-', dir=scratch) as name:
        temp = Path(name)
        (temp / 'native/entry_return').mkdir(parents=True)
        (temp / 'native/road').mkdir(parents=True)
        shutil.copy2(ROOT / 'native/road/road.xodr', temp / 'native/road/road.xodr')
        for policy in POLICIES:
            src = ROOT / 'native/entry_return' / policy
            dst = temp / 'native/entry_return' / policy
            shutil.copytree(src, dst)
        check(temp)
        policy = POLICIES[0]
        track = temp / 'native/entry_return' / policy / 'requested-tracks.jsonl'
        rows = [json.loads(line) for line in track.read_text().splitlines()]
        rows[800]['requested_approaching_world_xy_m'][0] += 7
        track.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
        negatives.append(rejected(lambda: check(temp), 'source binding changed'))
        shutil.copy2(ROOT / 'native/entry_return' / policy / 'requested-tracks.jsonl', track)
        config_path = temp / 'native/entry_return' / policy / 'config.json'
        config = json.loads(config_path.read_text())
        config['duration_s'] = 30
        config_path.write_text(json.dumps(config, indent=2) + '\n')
        negatives.append(rejected(lambda: check(temp), 'source binding changed'))
        shutil.copy2(ROOT / 'native/entry_return' / policy / 'config.json', config_path)
        road = temp / 'native/road/road.xodr'
        road.write_text(road.read_text().replace('length="140"', 'length="139"', 1))
        negatives.append(rejected(lambda: check(temp), 'source binding changed'))
        shutil.copy2(ROOT / 'native/road/road.xodr', road)
        for policy in POLICIES:
            track = temp / 'native/entry_return' / policy / 'requested-tracks.jsonl'
            rows = [json.loads(line) for line in track.read_text().splitlines()]
            rows[802]['requested_approaching_world_xy_m'][0] += 7
            track.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
            config_path = temp / 'native/entry_return' / policy / 'config.json'
            config = json.loads(config_path.read_text())
            config['requested_tracks_sha256'] = sha(track)
            config_path.write_text(json.dumps(config, indent=2) + '\n')
            if policy == POLICIES[0]:
                negatives.append(rejected(lambda: check(temp),
                    'approaching context differs'))
    return {
        'format': 'roadway-entry-return-request-cpu-proof',
        'passed': True,
        'positive': positive,
        'negative_errors': negatives,
        'request_builder_sha256': sha(ROOT / 'native/build_entry_return.py'),
        'request_checker_sha256': sha(ROOT / 'native/check_entry_return.py'),
        'runner_sha256': sha(ROOT / 'native/runner_entry_return.py'),
        'carla_started': False,
        'physical_or_legal_outcome_claimed': False,
    }


if __name__ == '__main__':
    output = ROOT / 'native/entry_return/request-proof.json'
    output.write_text(json.dumps(run(), indent=2) + '\n')
    print(json.dumps({'passed': True, 'proof': str(output.relative_to(ROOT)),
                      'sha256': sha(output)}))
