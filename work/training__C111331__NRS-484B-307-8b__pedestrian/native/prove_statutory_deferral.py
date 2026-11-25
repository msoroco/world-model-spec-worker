"""Source-bound check of all four referenced 484B.283 subparagraphs."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ASSIGNMENT = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove(source, review, plan):
    source_laws = json.loads(Path(source).read_text())['laws']
    record = json.loads(Path(review).read_text())
    planned = json.loads(Path(plan).read_text())
    if record['source_sha256'] != sha(source):
        raise ValueError('Frozen NRS 484B.283 source changed')
    keys = ['NRS-484B-283-1d' + str(n) for n in range(1, 5)]
    if [item['law_id'] for item in record['referenced_provisions']] != keys:
        raise ValueError('NRS 484B.283 referenced provisions incomplete')
    for item in record['referenced_provisions']:
        original = source_laws[item['law_id']]['law']
        if (item['exact_text'], item['source']) != (original['text'], original['source']):
            raise ValueError('NRS 484B.283 source quote differs')
    by_id = {case['case_id'].split('__')[-1]: case for case in planned['cases']}
    if not {'condition_a', 'condition_b', 'exception_absent',
            'exception_permits', 'exception_countdown'} <= set(by_id):
        raise ValueError('Walk and countdown entry permissions not both planned')
    comparisons = {item['comparison_id'].split('__')[-1] for item in planned['comparisons']}
    if not {'red_entry_contrast', 'other_device_permission_contrast',
            'countdown_permission_contrast'} <= comparisons:
        raise ValueError('Both permission comparisons required')
    if by_id['exception_countdown']['planning_status'] != 'native_debug_display_authored_original_unverified':
        raise ValueError('Countdown debug-display and original review status must remain explicit')
    return {'format': 'c111331-statutory-deferral-cpu-proof-v1',
            'referenced_laws': keys, 'planned_cases': len(by_id),
            'planned_comparisons': len(comparisons),
            'countdown_original_constructed': False,
            'legal_verdict_claimed': False}


def main():
    source = ROOT / 'inputs/coverage/branch-sources.json'
    review = ASSIGNMENT / 'statutory-deferral-review.json'
    plan = ASSIGNMENT / 'case-plan.json'
    result = prove(source, review, plan)
    target = ASSIGNMENT / 'statutory-deferral-proof.json'
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'receipt_sha256': sha(target), 'referenced_laws': len(result['referenced_laws'])}))


if __name__ == '__main__':
    main()
