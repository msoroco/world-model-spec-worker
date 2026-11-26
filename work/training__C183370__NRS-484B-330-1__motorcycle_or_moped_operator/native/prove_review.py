"""Exercise independent review bindings on source-shaped synthetic attempts."""

import json
from pathlib import Path
import tempfile

from measure_original import CAMERAS, REVIEW_COPIES, sha
from prove_original import fixture
from review_original import OBSERVATIONS, review


def prove():
    scratch = Path('.runtime-work/c183370-review-proof').resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    outcomes = []
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        for suffix in ('probe_a', 'probe_b'):
            attempt = Path(directory) / suffix
            attempt.mkdir()
            case_id = fixture(attempt, suffix)
            seal = json.loads((attempt / 'captured-source-hashes.json').read_text())
            receipt = {
                'format': 'c183370-original-review-v1',
                'source_kind': 'synthetic_structural_review',
                'case_id': case_id, 'reviewer': 'fixture source-binding test',
                'source_seal_sha256': sha(attempt / 'captured-source-hashes.json'),
                'frame_count': 600, 'rate_hz': 20,
                'reviewed_sha256': {name: seal['sha256'][name] for name in
                    list(REVIEW_COPIES.values()) +
                    [camera + '.mkv' for camera in CAMERAS]},
                'observations': {name: {'camera': 'flagger' if name.startswith('signal')
                    or name == 'flagger_identity' else 'overview',
                    'video_frame': 150 if name == 'signal_stop' else 350,
                    'observed': False,
                    'note': 'synthetic shape only; original pixels unreviewed'}
                    for name in OBSERVATIONS},
            }
            receipt_path = attempt / 'review-receipt.json'
            receipt_path.write_text(json.dumps(receipt) + '\n')
            checked = review(attempt, case_id, receipt_path)
            assert checked['binding_passed'] and not checked['original_pixel_reviewed']
            assert checked['physical_completion'] is None
            outcomes.append({'case_id': case_id, 'synthetic_binding_passed': True})
            for changed, expected in (
                    ({'source_seal_sha256': '0' * 64}, 'source seal differs'),
                    ({'reviewed_sha256': {}}, 'source hashes differ'),
                    ({'observations': {}}, 'observations incomplete'),
                    ({'source_kind': 'original_pixel_review'}, 'observation unresolved')):
                rejected = dict(receipt, **changed)
                receipt_path.write_text(json.dumps(rejected) + '\n')
                try:
                    review(attempt, case_id, receipt_path)
                except ValueError as error:
                    if expected not in str(error):
                        raise
                else:
                    raise AssertionError('Altered review receipt accepted')
            invalid_frame = dict(receipt, observations={
                name: dict(item, video_frame=True) if name == 'signal_stop' else item
                for name, item in receipt['observations'].items()})
            receipt_path.write_text(json.dumps(invalid_frame) + '\n')
            try:
                review(attempt, case_id, receipt_path)
            except ValueError as error:
                assert 'observation invalid' in str(error)
            else:
                raise AssertionError('Boolean video frame accepted')
            declared = dict(receipt, source_kind='original_pixel_review',
                            observations={name: dict(item, observed=True)
                                          for name, item in receipt['observations'].items()})
            receipt_path.write_text(json.dumps(declared) + '\n')
            checked = review(attempt, case_id, receipt_path)
            assert checked['review_receipt_declares_original_observations']
            assert checked['original_pixel_reviewed'] is None
            assert checked['physical_completion'] is None
            receipt_path.write_text(json.dumps(receipt) + '\n')
    return {'format': 'c183370-review-binding-proof',
            'source_kind': 'synthetic_structural_fixture',
            'positive_count': 4, 'negative_count': 10, 'cases': outcomes,
            'original_pixels_reviewed': False,
            'physical_or_legal_outcome_claimed': False}


if __name__ == '__main__':
    print(json.dumps(prove()))
