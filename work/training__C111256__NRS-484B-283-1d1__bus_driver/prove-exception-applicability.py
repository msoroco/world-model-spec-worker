"""Exercise cited exception review schema and synthetic-original rejection."""
import copy
import hashlib
import json
from pathlib import Path

from exception_applicability_audit import (QUESTIONS, SOURCES, audit_original,
                                           sha, validate_review)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ATTEMPT = ROOT / '.runtime-work/c111256-update025-selected/reference/primary/selected-attempt'


def reject(call, expected):
    try:
        call()
    except ValueError as error:
        if expected not in str(error):
            raise
    else:
        raise ValueError('Exception audit accepted ' + expected)


def main():
    hashes = {name: sha(ATTEMPT / name) for name in SOURCES}
    checks = {}
    for name, section in QUESTIONS.items():
        checks[name] = {'section': section, 'observed': False,
                        'method': 'CPU schema exercise only',
                        'coverage_complete': True,
                        'evidence': [{'source': 'overview.mkv',
                                      'sha256': hashes['overview.mkv'],
                                      'frame_range': [0, 479],
                                      'observation': 'synthetic shape placeholder',
                                      'limitations': 'No original actor or pixel review'}]}
    review = {'format': 'c111256-exception-applicability-review-v1',
              'source_kind': 'source_shaped_unit_test',
              'source_sha256': hashes, 'reviewer': 'CPU schema test',
              'method': 'Source-shaped contract only',
              'legal_verdict_claimed': False, 'checks': checks}
    positive = validate_review(review, hashes, diagnostic=True)
    if positive['reviewed_branches'] != 7 or positive['ordinary_marked_crosswalk_scope_supported']:
        raise ValueError('Diagnostic exception review promoted to original scope')
    damaged = copy.deepcopy(review)
    damaged['checks'].pop('school_crossing_guard_direction_or_signal')
    reject(lambda: validate_review(damaged, hashes, diagnostic=True),
           'Cited exception branch review incomplete')
    damaged = copy.deepcopy(review)
    damaged['checks']['blind_pedestrian_using_service_animal_or_qualifying_cane'][
        'evidence'][0]['sha256'] = '0' * 64
    reject(lambda: validate_review(damaged, hashes, diagnostic=True),
           'Exception branch source or frame coverage differs')
    damaged = copy.deepcopy(review)
    damaged['source_kind'] = 'original_native_exception_review'
    reject(lambda: validate_review(damaged, hashes, diagnostic=True),
           'Exception review identity, provenance or source hashes differ')
    reject(lambda: audit_original(ATTEMPT, HERE / 'nonexistent-exception-review.json'),
           'Synthetic source cannot prove exception applicability')
    print(json.dumps({'format': 'c111256-exception-applicability-cpu-proof-v1',
                      'source_shaped_branches': 7, 'negative_rejections': 4,
                      'original_exception_applicability_verified': False,
                      'legal_verdict_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
