"""Independent eight-receipt and controlled synthetic source-pair audit."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import shutil

FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(FOLDER / 'native'))
from measure_u_turn import measure


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest = json.loads((FOLDER / 'draft-execution-manifest.json').read_text())
    proof = json.loads((FOLDER / 'exact-saved-proof.json').read_text())
    if proof['passed'] is not True or proof['selected'] is not False or len(proof['rows']) != 8:
        raise AssertionError('Exact saved proof incomplete or mislabeled')
    expected = set()
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            source = entry if candidate == 'primary' else next(c for c in entry['candidates'] if c['id'] == candidate)
            if digest(FOLDER / source['construction']) != source['construction_sha256']:
                raise AssertionError('Construction source changed')
            expected.add((entry['case_id'], candidate, source['construction_sha256']))
    actual = {(r['case_id'],r['candidate_id'],r['construction_sha256']) for r in proof['rows']}
    if actual != expected:
        raise AssertionError('Exact saved proof does not cover every bundle')
    fixed = {}
    for suffix, name, observed in (('witness_1','straight',False),('witness_2','u_turn',True)):
        fixture = FOLDER / 'draft-u-turn-saved' / name
        with tempfile.TemporaryDirectory() as temp:
            video = Path(temp) / 'approach.mkv'
            shutil.copyfile(fixture / 'approach-video-fixture.txt', video)
            value = measure(fixture / 'native_samples.jsonl', fixture / 'video_frames.jsonl',
                            fixture / 'sign-review.json', video)
            if value['u_turn_within_governed_region_observed'] is not observed:
                raise AssertionError('Controlled source result changed')
            fixed[suffix] = {'samples_sha256': digest(fixture / 'native_samples.jsonl'),
                             'frame_map_sha256': digest(fixture / 'video_frames.jsonl'),
                             'sign_review_sha256': digest(fixture / 'sign-review.json'),
                             'video_fixture_sha256': digest(video)}
        rows = [r for r in proof['rows'] if r['case_id'].endswith('__' + suffix)]
        if len(rows) != 4 or any(r['observed_in_synthetic_fixture'] is not observed or
                                 r['positive_contract_verified'] is not True or
                                 r['missing_native_source_rejected'] is not True for r in rows):
            raise AssertionError('Candidate saved results differ from controlled pair')
    return {'passed': True, 'exact_unselected_bundles': 8,
            'controlled_signed_u_turn_results': {'witness_1': False, 'witness_2': True},
            'fixed_sources': fixed, 'native_executed': False, 'selected': False}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
