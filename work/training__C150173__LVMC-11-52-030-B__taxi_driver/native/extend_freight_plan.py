"""Bind the same-cell taxi/light-express controlled branch without legal inference."""
import json
from pathlib import Path

from freight_plan import PREFIX, PURPOSES


PACKAGE = Path(__file__).resolve().parent.parent


def main():
    path = PACKAGE / 'case-plan.json'
    plan = json.loads(path.read_text())
    ids = [PREFIX + suffix for suffix in PURPOSES]
    disposition = next(row for row in plan['requirement_dispositions']
                       if row['branch'] == 'commercial freight alternative')
    disposition['status'] = 'selected_required'
    disposition['case_ids'] = ids
    disposition['evidence_or_gap'] = (
        'Three selected same-cell taxi/light-express cargo constructions contrast loading, '
        'unloading and no transfer with original taxi and cargo actor IDs, saved body vertices, '
        'four cameras and independent classification, sign and purpose source reviews. '
        'Original commercial status, sign authority and actual freight purpose remain unresolved.')
    existing = {row['case_id'] for row in plan['cases']}
    targets = {
        'freight_load': 'stopped taxi with light-express cargo moved toward taxi; commercial identity, effective sign and actual loading require original review',
        'freight_unload': 'stopped taxi with light-express cargo moved away from taxi; commercial identity, effective sign and actual unloading require original review',
        'freight_wait': 'same stopped taxi and cargo proxy without transfer; negative control, original purpose and identity unresolved',
    }
    for suffix, target in targets.items():
        case = PREFIX + suffix
        if case not in existing:
            plan['cases'].append({'case_id': case, 'target_law_id': plan['law_id'],
                'kind': 'planned_only', 'target_type': 'measurement_attempt',
                'physical_target': target,
                'comparison_variable': 'light_express_freight_transfer'})
    existing_comparisons = {row['comparison_id'] for row in plan['comparisons']}
    for suffix in ('freight_load', 'freight_unload'):
        comparison_id = PREFIX + suffix + '_comparison'
        if comparison_id not in existing_comparisons:
            plan['comparisons'].append({
                'comparison_id': comparison_id,
                'case_ids': [PREFIX + 'freight_wait', PREFIX + suffix],
                'fixed_conditions': ['same taxi-driver actor role and authored one-way yellow curb',
                    'same proposed commercial-freight 09:00–17:00 sign',
                    'same requested taxi stop and cargo proxy blueprint',
                    'same 10:00 civil time, four 20 Hz views and 600-frame interval'],
                'deliberate_differences': [
                    'no cargo transfer versus ' + ('cargo toward taxi' if suffix == 'freight_load'
                                                   else 'cargo away from taxi')],
                'independent_source_review_required': [
                    'original taxi identity and commercial-use classification',
                    'actual freight cargo and purpose',
                    'effective authoritative sign and curb zone']})
    plan['source_observation_mapping']['ru.commercial_motor_vehicle'] = {
        'evidence': 'The original taxi actor ID must join source-based identity and commercial-use classification; the actor role or case label is insufficient.',
        'channels': ['ru.commercial_motor_vehicle'],
        'source_refs': ['freight-native.jsonl', 'commercial-status-review.json']}
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'cases': len(plan['cases']), 'comparisons': len(plan['comparisons']),
                      'freight_ids': ids}))


if __name__ == '__main__':
    main()
