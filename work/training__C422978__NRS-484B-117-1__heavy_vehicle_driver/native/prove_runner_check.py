"""Retain CPU evidence that exact capture entry points bind all eight requests."""
import hashlib
import json
from pathlib import Path

import runner

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejected(fn):
    try:
        fn()
    except ValueError:
        return True
    raise AssertionError('Runner accepted altered identity or source')


def prove():
    positives = []
    for case in runner.CASES:
        for candidate in runner.CANDIDATES:
            bundle = HERE/'drafts'/case/candidate
            result = runner.check(bundle, case, candidate)
            assert result['passed'] and not result['carla_imported']
            positives.append({'case': case, 'candidate': candidate,
                              'config_sha256': digest(bundle/'config.json'),
                              'tracks_sha256': digest(bundle/'requested-tracks.jsonl')})
    bundle = HERE/'drafts'/'reference'/'primary'
    negatives = {
        'wrong_case': rejected(lambda: runner.check(bundle, 'contrast', 'primary')),
        'wrong_candidate': rejected(lambda: runner.check(bundle, 'reference', 'fallback1')),
        'unknown_candidate': rejected(lambda: runner.check(bundle, 'reference', 'fallback4')),
    }
    original = runner.sha
    try:
        runner.sha = lambda path: '0'*64 if Path(path) == HERE/'road.xodr' else original(path)
        negatives['changed_road_hash'] = rejected(
            lambda: runner.check(bundle, 'reference', 'primary'))
    finally:
        runner.sha = original
    result = {'format': 'c422978-heavy-native-runner-cpu-check-v1',
              'runner_sha256': digest(HERE/'runner.py'),
              'positives': positives, 'negatives': negatives,
              'original_native_observed': False, 'delivery_ready': False}
    (HERE/'runner-check-proof.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    print(json.dumps({'positives': len(prove()['positives']), 'negatives': 4}))
