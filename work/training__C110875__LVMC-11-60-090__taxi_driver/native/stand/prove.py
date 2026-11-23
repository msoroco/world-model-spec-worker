"""Current-source request positives and rehashed material negatives."""
import copy
import json
from pathlib import Path
import shutil
import tempfile

from check import check, sha
from request import CASES, HERE, build


def rejected(bundle, mutate):
    with tempfile.TemporaryDirectory() as temp:
        copied = Path(temp) / 'bundle'
        shutil.copytree(bundle, copied)
        mutate(copied)
        try:
            check(copied)
        except (ValueError, KeyError, TypeError):
            return True
        return False


def mutate_track(bundle, kind):
    path = bundle / 'requested-tracks.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if kind == 'first':
        for row in rows:
            row['first_intersection_station_m'] = 130.0
    elif kind == 'turn':
        rows[350]['requested_heading_deg'] = 90 if rows[350]['requested_heading_deg'] == 0 else 0
    elif kind == 'authority':
        rows[350]['posted_notice_verified'] = True
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    cfg = json.loads((bundle / 'config.json').read_text())
    cfg['tracks_sha256'] = sha(path)
    (bundle / 'config.json').write_text(json.dumps(cfg, indent=2) + '\n')


def prove():
    manifest = build()
    positives = negatives = 0
    for suffix in CASES:
        bundle = HERE / 'drafts' / suffix
        result = check(bundle)
        if result['delivery_ready'] or result['original_native_observed']:
            raise ValueError('Diagnostic request promoted')
        positives += 1
        for kind in ('first', 'turn', 'authority'):
            if not rejected(bundle, lambda copied, k=kind: mutate_track(copied, k)):
                raise ValueError('Rehashed route tamper passed: ' + kind)
            negatives += 1
        if not rejected(bundle, lambda copied: (copied / 'assignment-source.json').write_text('{}\n')):
            raise ValueError('Changed source passed')
        negatives += 1
    receipt = {'format': 'c110875-taxi-request-proof-v1',
               'assignment_id': manifest['assignment_id'],
               'manifest_sha256': sha(HERE / 'manifest.json'),
               'positives': positives, 'negatives': negatives,
               'frames_per_case': 600, 'rate_hz': 20,
               'synthetic_or_authored_requests_only': True,
               'original_native_observed': False, 'delivery_ready': False}
    (HERE / 'request-proof.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    print(json.dumps(prove()))
