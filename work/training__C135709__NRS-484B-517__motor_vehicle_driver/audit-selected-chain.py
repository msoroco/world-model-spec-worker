"""Independently audit eight pinned compatibility and saved-processing chains."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def audit():
    compatibility = read(ROOT/'update051-proof-matrix.json')
    saved = read(ROOT/'update051-saved-matrix.json')
    expected = {(ROOT.name+'__'+witness, candidate)
        for witness in ('reference', 'contrast')
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')}
    if not compatibility['all_passed'] or not saved['all_passed']:
        raise ValueError('Selected chain contains failed proof')
    crows = {(r['case_id'], r['candidate_id']): r for r in compatibility['results']}
    srows = {(r['case_id'], r['candidate_id']): r for r in saved['results']}
    if set(crows) != expected or set(srows) != expected:
        raise ValueError('Selected chain coverage differs')
    counts = {}
    for case_id, candidate in sorted(expected):
        witness = case_id.split('__')[-1]
        c, s = crows[case_id, candidate], srows[case_id, candidate]
        if c['exit_code'] != 0 or s['exit_code'] != 0:
            raise ValueError('Selected chain exit failed')
        manifest = ROOT/c['manifest']
        recipe = REPO/c['fixture_recipe']
        if (sha(manifest) != c['manifest_sha256'] or
            sha(recipe) != c['fixture_recipe_sha256'] or
            s['manifest_sha256'] != c['manifest_sha256'] or
            s['recipe_sha256'] != c['fixture_recipe_sha256'] or
            sha(ROOT/c['log']) != c['log_sha256'] or
            sha(ROOT/s['log']) != s['log_sha256']):
            raise ValueError('Selected command/source hash differs')
        proof = ROOT/'update051-proof'/witness/candidate
        saved_proof = ROOT/'update051-saved'/witness/candidate
        for name in ('receipt.json', 'analysis.log', 'negative.log'):
            if sha(proof/name) != c[name+'_sha256']:
                raise ValueError('Compatibility proof file changed')
        if sha(saved_proof/'processing.json') != s['processing_sha256']:
            raise ValueError('Saved processing proof file changed')
        receipt = read(proof/'receipt.json')
        processing = read(saved_proof/'processing.json')
        if (receipt['passed'] is not True or
            receipt['case_id'] != case_id or receipt['candidate_id'] != candidate or
            receipt['fixture_recipe_sha256'] != c['fixture_recipe_sha256'] or
            receipt['negative_removed'] != 'stand-review.jsonl' or
            'negative_case_source' not in receipt['checks'] or
            'four_camera_sources' not in receipt['checks'] or
            'Missing required source: stand-review.jsonl' not in (proof/'negative.log').read_text() or
            processing['originals_preserved'] is not True or
            processing['missing_evidence'] is not False or
            processing['physical_acceptance_claimed'] is not False or
            processing['legal_acceptance_claimed'] is not False):
            raise ValueError('Compatibility or saved receipt lacks source/negative checks')
        compatible = REPO/'.runtime-work/update054-c135709-compat-all-v4'/witness/candidate
        processed = (REPO/'.runtime-work/update054-c135709-saved-all-v4'/witness/
                     candidate/'processed/v0001/analysis')
        a = read(compatible/'analysis-report.json')
        b = read(processed/'analysis-report.json')
        if (a['measurements'] != b['measurements'] or
            a['source_kind'] != 'synthetic_cpu' or b['source_kind'] != 'synthetic_cpu' or
            sha(compatible/'native-raw-actors.jsonl') != sha(processed/'native-raw-actors.jsonl') or
            sha(compatible/'stand-review.jsonl') != sha(processed/'stand-review.jsonl')):
            raise ValueError('Actual saved processing differs from compatibility source measurement')
        measured = a['measurements']['sampled_stand_occupancy_frames']['value']
        if (witness == 'reference' and measured != 0) or (
                witness == 'contrast' and measured < 30):
            raise ValueError('Selected stand occupancy control differs')
        for output in (compatible, processed):
            result = read(output/'result.json')
            if (result['accepted'] is not False or
                result['setup_confirmed'] is not False or
                result['maneuver_completed'] is not False or
                result['measured_values']['sampled_stand_occupancy_frames'] != measured or
                len(result['video_references']) != 4):
                raise ValueError('Selected result makes unsupported physical claim')
        counts[(witness, candidate)] = measured
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        if counts['reference', candidate] >= counts['contrast', candidate]:
            raise ValueError('Controlled stand occupancy comparison vanished')
    result = {'format': 'c135709-independent-selected-chain-audit-v1',
        'compatibility_matrix_sha256': sha(ROOT/'update051-proof-matrix.json'),
        'saved_matrix_sha256': sha(ROOT/'update051-saved-matrix.json'),
        'candidates_checked': len(expected),
        'reference_occupied_frames': [counts['reference', c] for c in
            ('primary', 'fallback1', 'fallback2', 'fallback3')],
        'contrast_occupied_frames': [counts['contrast', c] for c in
            ('primary', 'fallback1', 'fallback2', 'fallback3')],
        'original_native_observed': False, 'delivery_ready': False}
    path = ROOT/'update051-selected-chain-audit.json'
    path.write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
