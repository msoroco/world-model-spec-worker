"""Positive and altered-source negatives for exact copied device bundles."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from check import check

HERE = Path(__file__).resolve().parent


def edit(path, key, value):
    data = json.loads(path.read_text())
    data[key] = value
    path.write_text(json.dumps(data) + '\n')


def edit_row(path, key, value):
    data = [json.loads(line) for line in path.read_text().splitlines()]
    data[100][key] = value
    path.write_text(''.join(json.dumps(row) + '\n' for row in data))


def alter_plan_law(bundle):
    path = bundle / 'case-plan.json'
    data = json.loads(path.read_text())
    data['source_law']['text'] = 'altered statutory text'
    path.write_text(json.dumps(data) + '\n')


def wrong_signal_with_rehash(bundle):
    road = bundle / 'alley-stop.xodr'
    content = road.read_text()
    changed = content.replace('type="206"', 'type="205"')
    if changed == content:
        raise ValueError('stop signal missing')
    road.write_text(changed)
    edit(bundle / 'config.json', 'road_sha256',
         hashlib.sha256(road.read_bytes()).hexdigest())


def rejected(bundle, change):
    with tempfile.TemporaryDirectory(prefix='c10389-request-negative-') as folder:
        target = Path(folder) / 'bundle'
        shutil.copytree(bundle, target)
        change(target)
        try:
            check(target)
        except (ValueError, KeyError, TypeError):
            return True
        return False


def prove():
    entries = json.loads((HERE / 'offline' / 'manifest.json').read_text())['entries']
    positives = negatives = 0
    for entry in entries:
        bundle = HERE / entry['bundle']
        result = check(bundle)
        if result['delivery_ready'] or result['official_placement_verified']:
            raise ValueError('unverified request promoted')
        positives += 1
        changes = (
            lambda d: edit(d / 'assignment-source.json', 'actor', 'pedestrian'),
            alter_plan_law,
            lambda d: edit(d / 'config.json', 'road_sha256', '0' * 64),
            lambda d: edit(d / 'config.json', 'route_policy', 'stop_before_device'
                           if result['requested_crossing'] else 'target'),
            lambda d: edit_row(d / 'requested-tracks.jsonl', 'requested_speed_mps', 99),
            wrong_signal_with_rehash,
            lambda d: edit(d / 'config.json', 'official_placement_verified', True),
        )
        for change in changes:
            if not rejected(bundle, change):
                raise ValueError('changed source accepted')
            negatives += 1
    proof = {'format': 'c10389-device-copied-compatibility-v1',
             'positives': positives, 'negatives': negatives,
             'original_native_observed': False, 'delivery_ready': False}
    (HERE / 'offline' / 'proof-compatibility.json').write_text(
        json.dumps(proof, indent=2) + '\n')
    return proof


if __name__ == '__main__':
    print(json.dumps(prove()))
