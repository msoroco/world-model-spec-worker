"""Run exact positive and tamper-negative checks for unselected requests."""
import json
import shutil
from pathlib import Path

from check import check
from request import CASES, CASE, HERE, sha


def expect_reject(bundle):
    try:
        check(bundle)
    except (ValueError, KeyError):
        return True
    raise AssertionError('Tampered request accepted')


def prove():
    temporary = CASE.parents[1] / '.runtime-work' / 'c109166-tamper'
    temporary.mkdir(parents=True, exist_ok=True)
    positives = []
    negatives = []
    for crossing in CASES:
        bundle = HERE / 'drafts' / crossing
        positives.append(check(bundle))
        for name in ('law', 'track', 'status', 'duration'):
            target = temporary / (crossing + '-' + name)
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(bundle, target)
            if name == 'law':
                data = json.loads((target / 'assignment-source.json').read_text())
                data['law']['text'] = 'altered law'
                (target / 'assignment-source.json').write_text(json.dumps(data) + '\n')
            elif name == 'track':
                path = target / 'requested-tracks.jsonl'
                lines = path.read_text().splitlines()
                row = json.loads(lines[260])
                row['requested_x_m'] += 1
                lines[260] = json.dumps(row)
                path.write_text('\n'.join(lines) + '\n')
            else:
                path = target / 'config.json'
                data = json.loads(path.read_text())
                data['status' if name == 'status' else 'duration_s'] = 'delivery_ready' if name == 'status' else 29
                path.write_text(json.dumps(data) + '\n')
            negatives.append({'crossing': crossing, 'tamper': name,
                              'rejected': expect_reject(target)})
    if len(positives) != 2 or len(negatives) != 8:
        raise AssertionError('Incomplete request proof')
    receipt = {'format': 'c109166-request-proof-v1', 'assignment_id': CASE.name,
               'manifest_sha256': sha(HERE / 'manifest.json'),
               'positives': positives, 'negatives': negatives,
               'native_observed': False, 'delivery_ready': False}
    (HERE / 'request-proof.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    value = prove()
    print(json.dumps({'positives': len(value['positives']),
                      'negatives': len(value['negatives'])}))
