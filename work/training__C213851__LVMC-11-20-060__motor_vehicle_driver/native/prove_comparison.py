"""Exercise fixed-context and changed-policy source joins on CPU fixtures."""

import json
import tempfile
from pathlib import Path

from audit_comparison import audit
from measure_sidewalk import sha
from prove_sidewalk import ASSIGNMENT, HERE, fixture, reseal, write_json, write_rows


def reject(left, right, expected):
    try:
        audit(left, right, ASSIGNMENT)
    except ValueError as exc:
        if expected not in str(exc):
            raise AssertionError(str(exc)) from exc
        return str(exc)
    raise AssertionError('Changed pair was accepted')


def main():
    with tempfile.TemporaryDirectory(prefix='c213851-comparison-') as tmp:
        root = Path(tmp)
        left = root / 'stop'
        right = root / 'cross'
        left.mkdir()
        right.mkdir()
        fixture(left, 'stop_before_sidewalk')
        fixture(right, 'cross_without_stop')
        positive = audit(left, right, ASSIGNMENT)
        site_path = right / 'site-review.json'
        site = json.loads(site_path.read_text())
        site['district_source_note'] = 'changed'
        write_json(site_path, site)
        reseal(right)
        negatives = [reject(left, right, 'context changed')]
        site.pop('district_source_note')
        write_json(site_path, site)
        rows_path = right / 'native-rows.jsonl'
        rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
        rows[5]['pedestrian_xy_m'][0] += .1
        write_rows(rows_path, rows)
        reseal(right)
        negatives.append(reject(left, right, 'pedestrian or capture context changed'))
    proof = {'format': 'road-to-driveway-comparison-proof', 'passed': True,
             'positive': positive, 'negative_count': len(negatives),
             'negative_errors': negatives, 'actual_original_pair_observed': False}
    path = HERE / 'sidewalk-comparison-proof.json'
    write_json(path, proof)
    print(json.dumps({'passed': True, 'negative_count': len(negatives),
                      'proof_sha256': sha(path)}))


if __name__ == '__main__':
    main()
