"""Bind nine sign-angle fallback compatibility and saved CPU receipts."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    manifest = json.loads((ROOT / 'sign-angle-compatibility-manifest.json').read_text())
    proofs = []
    for entry in manifest['cases']:
        label = entry['case_id'].split('sign_angle_')[1]
        recipe = REPO / entry['fixture_recipe']
        for candidate in entry['candidates']:
            ident = candidate['id']
            construction = ROOT / candidate['construction']
            require(sha(construction) == candidate['construction_sha256'],
                    'Fallback construction changed')
            compat = REPO / f'.runtime-work/c158190-sign-angle-{label}-{ident}-compat-v1'
            receipt = json.loads((compat / 'compatibility.json').read_text())
            require(receipt.get('format') == 'worker-package-compatibility'
                    and receipt.get('passed') is True
                    and receipt.get('case_id') == entry['case_id']
                    and receipt.get('candidate_id') == ident
                    and receipt.get('construction_sha256') == candidate['construction_sha256']
                    and receipt.get('fixture_recipe_sha256') == sha(recipe)
                    and receipt.get('negative_removed') == 'visibility_rays.jsonl'
                    and {'selected_measurements', 'negative_case_source',
                         'lean_decoder', 'final_decode'} <= set(receipt.get('checks', [])),
                    'Positive or negative exact compatibility differs')
            require(sha(compat / 'compatibility-analysis.log') == receipt['log_sha256']
                    and sha(compat / 'negative-analysis.log') == receipt['negative_log_sha256'],
                    'Compatibility analysis log changed')
            saved = REPO / f'.runtime-work/c158190-sign-angle-{label}-{ident}-saved-v1/v0001/processing.json'
            processing = json.loads(saved.read_text())
            require(processing.get('passed') is True
                    and processing.get('candidate_id') == ident
                    and processing.get('recorded_only') is True
                    and processing.get('originals_preserved') is True
                    and processing.get('physical_acceptance_claimed') is False
                    and processing.get('legal_acceptance_claimed') is False,
                    'Recorded-only fallback processing incomplete')
            proofs.append({'case_id': entry['case_id'], 'candidate_id': ident,
                           'construction_sha256': sha(construction),
                           'fixture_recipe_sha256': sha(recipe),
                           'compatibility_sha256': sha(compat / 'compatibility.json'),
                           'positive_log_sha256': receipt['log_sha256'],
                           'negative_log_sha256': receipt['negative_log_sha256'],
                           'saved_processing_sha256': sha(saved),
                           'candidate_road_matches_synthetic_source': ident != 'fallback1'})
    require(len(proofs) == 9, 'Nine exact fallbacks required')
    print(json.dumps({'format': 'c158190-sign-angle-fallback-saved-proof',
                      'fallbacks': proofs, 'all_cpu_paths_passed': True,
                      'source_kind': 'synthetic compatibility diagnostics',
                      'native_fallback_effect_proven': False,
                      'original_pixel_face_proven': False,
                      'legal_conclusion': 'unresolved'}, indent=2))


if __name__ == '__main__':
    main()
