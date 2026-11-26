"""Exercise independent comparison positives and fixed-source negatives."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

from comparison_audit import audit
from prove_saved_packet import make_attempt, sha
from saved_measure import process


def rejected(inside, outside, mutation, expected, folder, name,
             inside_attempt, outside_attempt):
    changed = copy.deepcopy(outside)
    mutation(changed)
    path = folder / (name + '.json')
    path.write_text(json.dumps(changed) + '\n')
    try:
        audit(inside, path, inside_attempt, outside_attempt)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError((expected, str(error))) from error
        return str(error)
    raise AssertionError('Invalid comparison was accepted: ' + name)


def main():
    with tempfile.TemporaryDirectory(prefix='c229954-comparison-', dir='.runtime-work') as temp:
        base = Path(temp)
        a = make_attempt(base / 'inside', True)
        b = make_attempt(base / 'outside', False)
        apath, bpath = base / 'inside-saved.json', base / 'outside-saved.json'
        process(a, apath)
        process(b, bpath)
        positive = audit(apath, bpath, a, b)
        assert positive['inside_rest_overlap_frames'] == 500
        assert positive['outside_rest_overlap_frames'] == 0
        other = json.loads(bpath.read_text())
        negatives = {
            'changed_device': rejected(apath, other,
                lambda value: value['measurement']['source_hashes'].__setitem__('device', '0' * 64),
                'Saved measurement differs', base, 'changed-device', a, b),
            'changed_activity': rejected(apath, other,
                lambda value: value.__setitem__('activity_mode_request', 'park'),
                'identities or activity', base, 'changed-activity', a, b),
            'outside_overlap': rejected(apath, other,
                lambda value: value['measurement'].__setitem__('rest_and_body_overlap_frames', 2),
                'Saved measurement differs', base, 'outside-overlap', a, b),
            'missing_measurement': rejected(apath, other,
                lambda value: value.pop('measurement'),
                'Saved measurement differs', base, 'missing-measurement', a, b),
            'legal_claim': rejected(apath, other,
                lambda value: value.__setitem__('legal_verdict_claimed', True),
                'cannot assert', base, 'legal-claim', a, b),
        }
        changed = make_attempt(base / 'different-device', False)
        device = changed / 'source-device.json'
        content = json.loads(device.read_text())
        content['content'] = 'different synthetic device content'
        device.write_text(json.dumps(content) + '\n')
        review = changed / 'source-review.json'
        inventory = json.loads(review.read_text())
        inventory['sources']['device']['sha256'] = sha(device)
        review.write_text(json.dumps(inventory) + '\n')
        changed_saved = base / 'different-device-saved.json'
        process(changed, changed_saved)
        try:
            audit(apath, changed_saved, a, changed)
        except ValueError as error:
            assert 'Fixed original' in str(error)
            negatives['valid_but_different_device'] = str(error)
        else:
            raise AssertionError('Different original device passed comparison')
        overlap = make_attempt(base / 'inside-as-outside', True)
        cfg = overlap / 'config.json'
        changed_cfg = json.loads(cfg.read_text())
        changed_cfg['case_id'] = changed_cfg['case_id'].replace('condition_a', 'condition_b')
        cfg.write_text(json.dumps(changed_cfg) + '\n')
        overlap_saved = base / 'inside-as-outside-saved.json'
        process(overlap, overlap_saved)
        try:
            audit(apath, overlap_saved, a, overlap)
        except ValueError as error:
            assert 'body-overlap difference absent' in str(error)
            negatives['valid_but_no_overlap_difference'] = str(error)
        else:
            raise AssertionError('Identical original overlap passed comparison')
        print(json.dumps({'format': 'worker-designated-comparison-cpu-proof',
                          'positive': positive, 'negative_rejections': negatives,
                          'synthetic_only': True}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
