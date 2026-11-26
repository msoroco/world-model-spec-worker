"""Synthetic structural positives and source negatives for comparison audit."""

import hashlib
import json
from pathlib import Path
import tempfile

from audit_comparison import audit
from prove_original import fixture


def expect_failure(a, b, fragment, pair):
    try:
        audit(a, b, pair=pair)
    except ValueError as error:
        if fragment not in str(error):
            raise
    else:
        raise AssertionError('Changed source comparison accepted')


def prove():
    scratch = Path('.runtime-work/c183370-comparison').resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    positives = 0
    negatives = 0
    with tempfile.TemporaryDirectory(dir=scratch) as folder:
        for pair in (('probe_a', 'probe_b'), ('probe_c', 'probe_d')):
            a = Path(folder) / pair[0]
            b = Path(folder) / pair[1]
            a.mkdir()
            b.mkdir()
            fixture(a, pair[0])
            fixture(b, pair[1])
            positive = audit(a, b, pair=pair)
            if (positive['observed_cross_frames'] != [2350, 2200] or
                    positive['requested_indications_at_crossing'] != ['release', 'stop'] or
                    positive['body_crossed_during_requested_stop'] != [False, True] or
                    positive['stopped_frames_during_requested_stop'] != [190, 0] or
                    positive['physical_completion'] is not None or
                    positive['case_ids'] != [
                        'training__C183370__NRS-484B-330-1__motorcycle_or_moped_operator__' + suffix
                        for suffix in pair]):
                raise AssertionError('Paired measured source audit differs')
            positives += 1
            review = b / 'original-flagger-review.json'
            original = review.read_text()
            review.write_text('{"source_review":"other"}\n')
            expect_failure(a, b, 'source missing or changed', pair)
            negatives += 1
            review.write_text(original)
            seal = b / 'captured-source-hashes.json'
            meta = json.loads(seal.read_text())
            altered_review = json.loads(original)
            altered_review['source_review'] = 'changed-and-resealed'
            review.write_text(json.dumps(altered_review) + '\n')
            meta['sha256']['original-flagger-review.json'] = hashlib.sha256(
                review.read_bytes()).hexdigest()
            seal.write_text(json.dumps(meta) + '\n')
            expect_failure(a, b, 'Paired original fixed source differs', pair)
            negatives += 1
            review.write_text(original)
            meta['sha256']['original-flagger-review.json'] = hashlib.sha256(
                review.read_bytes()).hexdigest()
            seal.write_text(json.dumps(meta) + '\n')
            road = b / 'road.xodr'
            road.write_text('<OpenDRIVE changed="1"/>\n')
            meta['sha256']['road.xodr'] = hashlib.sha256(
                road.read_bytes()).hexdigest()
            seal.write_text(json.dumps(meta) + '\n')
            expect_failure(a, b, 'Paired original fixed source differs', pair)
            negatives += 1
    return {'format': 'c183370-comparison-source-shape-proof',
            'synthetic_structural_only': True, 'positive_count': positives,
            'negative_count': negatives, 'original_native_observed': False,
            'full_video_decoded': False, 'physical_or_legal_outcome_claimed': False}


if __name__ == '__main__':
    print(json.dumps(prove()))
