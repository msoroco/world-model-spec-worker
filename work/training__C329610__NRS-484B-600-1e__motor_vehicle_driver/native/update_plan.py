"""Record the source-law boundary review and all three construction requests."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name
PLAN = ROOT / 'case-plan.json'


def main():
    obj = json.loads(PLAN.read_text())
    cases = obj['cases']
    if not any(c['case_id'] == AID + '__probe_at' for c in cases):
        cases.insert(1, {
            'case_id': AID + '__probe_at',
            'target_law_id': 'NRS-484B-600-1e',
            'kind': 'draft_cpu_offline_only',
            'target_type': 'boundary_attempt',
            'physical_target': 'drive at 80 mph',
            'comparison_variable': 'vehicle_speed_mph',
        })
    for case in cases:
        case['kind'] = 'draft_cpu_offline_only'
        case['construction'] = 'draft-native/' + case['case_id'].removeprefix(AID + '__') + '/construction.json'
    ids = [c['case_id'] for c in cases]
    obj['requirement_dispositions'][0]['case_ids'] = ids
    obj['requirement_dispositions'][0]['evidence_or_gap'] = (
        '75, 80 and 85 mph controller requests have exact 30-second, 600-frame '
        'same-cell left-turn offline constructions; original Native speed, selected '
        'compatibility and independent delivery evidence remain unverified.')
    obj['comparisons'][0]['case_ids'] = ids
    obj['construction_checkpoint'] = {
        'manifest': 'draft-native-manifest.json',
        'comparison_proof': 'native/request-comparison-proof.json',
        'selected': False,
        'original_native_observed': False,
        'boundary_targets_mph': [75, 80, 85],
    }
    obj['evidence_review'] = {
        'source': 'inputs/' + AID + '/review-context/review.json',
        'reviewed_memberships': [
            {'recording_id': row['recording_id'],
             'historical_case_id': row['case_id'],
             'demonstrated': row['description'] + '; accepted membership only',
             'limitations': 'No local original recording, trace, receipt or exact source-hashed equivalence is supplied.',
             'reuse': False}
            for row in json.loads((Path('inputs') / AID / 'review-context/review.json').read_text())
                ['comparisons'][0]['cases']],
        'new_evidence_reason': 'Three exact current-runtime constructions are required for source-bound CPU delivery proof; they do not replay accepted originals.',
    }
    PLAN.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
