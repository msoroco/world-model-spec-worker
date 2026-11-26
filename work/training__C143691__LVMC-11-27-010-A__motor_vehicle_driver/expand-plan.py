"""Expand the exact frozen trail cell into source-specific controlled comparisons."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / 'case-plan.json'
AID = HERE.name
SOURCE = 'LVMC 11.27.010(A); with 11.27.010(B)'
BRANCH = 'Conjunctive trail prerequisites, subject to all Subsection (B) exceptions'


def main():
    plan = json.loads(PLAN.read_text())
    variants = {
        'outside': ('outside', 'ordinary', True, True, True),
        'all_present': ('within', 'ordinary', True, True, True),
        'no_designation': ('within', 'ordinary', False, True, True),
        'no_dedication': ('within', 'ordinary', True, False, True),
        'no_posting': ('within', 'ordinary', True, True, False),
        'emergency': ('within', 'emergency_vehicle', True, True, True),
        'maintenance': ('within', 'right_of_way_maintenance', True, True, True),
    }
    cases = []
    for suffix, (route, subject, designated, dedicated, posted) in variants.items():
        cases.append({
            'case_id': AID + '__' + suffix,
            'target_law_id': 'LVMC-11-27-010-A',
            'kind': 'delivery',
            'target_type': 'controlled_attempt',
            'physical_target': f'{subject} route {route} trail right-of-way',
            'comparison_variable': 'trail_occupancy_or_source_condition',
            'source_branch': BRANCH,
            'requested_not_measured': True,
            'selection_targets': ['full-train'],
            'source_context_request': {
                'official_designation': designated,
                'city_dedication': dedicated,
                'appropriate_posting': posted,
                'exception_kind': subject if subject != 'ordinary' else 'none',
            },
        })
    plan['cases'] = cases
    pairings = {
        'occupancy': ('outside', 'all_present', 'trail_occupancy'),
        'designation': ('all_present', 'no_designation', 'official_trails_plan_designation'),
        'dedication': ('all_present', 'no_dedication', 'city_trail_dedication'),
        'posting': ('all_present', 'no_posting', 'appropriate_prohibition_sign'),
        'emergency': ('all_present', 'emergency', 'emergency_vehicle_identity'),
        'maintenance': ('all_present', 'maintenance', 'maintenance_of_this_right_of_way'),
    }
    plan['comparisons'] = [{
        'comparison_id': AID + '__' + label,
        'case_ids': [AID + '__' + left, AID + '__' + right],
        'deliberate_differences': [variable],
        'fixed_conditions': ['C143691 nonmotorized_trail / travel / barrier',
                             '30 seconds at 20 Hz with four source cameras',
                             'same corridor geometry and movement request except declared variable'],
    } for label, (left, right, variable) in pairings.items()]
    descriptions = [
        ('trail_occupancy', ['outside', 'all_present']),
        ('official_trails_plan_designation', ['all_present', 'no_designation']),
        ('city_trail_dedication', ['all_present', 'no_dedication']),
        ('appropriate_prohibition_sign', ['all_present', 'no_posting']),
        ('emergency_vehicle_exception', ['all_present', 'emergency']),
        ('right_of_way_maintenance_exception', ['all_present', 'maintenance']),
    ]
    plan['requirement_dispositions'] = [{
        'requirement': 'LVMC-11-27-010-A', 'source': SOURCE, 'branch': name,
        'status': 'selected_required',
        'case_ids': [AID + '__' + suffix for suffix in suffixes],
        'evidence_or_gap': ('Selected CPU comparison measures original source context and route. '
                            'Official records, sign appropriateness, exception identity, '
                            'physical realization and legal outcome await independent review.'),
    } for name, suffixes in descriptions]
    plan['requirement_dispositions'].append({
        'requirement': 'LVMC-11-27-010-A', 'source': SOURCE,
        'branch': 'mobility_device_exception', 'status': 'alternative_pending',
        'case_ids': [],
        'evidence_or_gap': ('Subsection (B)(3) needs a motorized wheelchair or other device '
                            'designed for and used by a mobility-impaired person. The frozen '
                            'actor is motor_vehicle_driver, and no eligible Native device or '
                            'operator binding is evidenced. A conventional vehicle is not '
                            'substituted for this exception. Original asset and actor eligibility '
                            'require source review before a selected comparison can be bound.'),
    })
    mapping = []
    for item in plan['mandatory_observation_terms']:
        term = item['term']
        if term == 'rel.occupies':
            measurement, evidence = 'trail_occupancy', ['vehicle-poses.jsonl', 'trail-inventory.json']
        elif term in ('dev.zone_sign', 'dev.regulatory_sign'):
            measurement, evidence = 'appropriate_prohibition_sign', ['trail-inventory.json', 'driver_reference.mkv']
        elif term in ('st.bicycle_lane_or_path', 'ru.animal_or_animal_drawn'):
            measurement, evidence = 'official_trails_plan_designation', ['trail-inventory.json', 'road.xodr']
        elif term == 'ru.emergency_vehicle':
            measurement, evidence = 'emergency_vehicle_exception', ['trail-inventory.json', 'vehicle-poses.jsonl']
        elif term == 'ru.official_vehicle':
            measurement, evidence = 'right_of_way_maintenance_exception', ['trail-inventory.json', 'vehicle-poses.jsonl']
        elif term == 'ru.pedestrian':
            measurement, evidence = 'mobility_device_exception', ['trail-inventory.json', 'vehicle-poses.jsonl']
        else:
            measurement, evidence = 'motorized_subject_identity', ['vehicle-poses.jsonl', 'trail-inventory.json']
        mapping.append({'term': term, 'measurement': measurement,
                        'evidence': evidence, 'channels': ['original Native trace', 'four source cameras'],
                        'source_refs': ['inputs/' + AID + '/assignment.json'],
                        'legal_outcome_claimed': False})
        item['status'] = ('actor_asset_eligibility_pending' if term == 'ru.pedestrian'
                          else 'mapped_pending_original_source_review')
    plan['source_observation_mapping'] = mapping
    plan['candidate_plans'] = []
    plan['selected_branch'] = BRANCH
    plan['blockers'] = ['Selected exact cases and source-bound CPU package are still being constructed.',
                        'Mobility-device exception actor/asset eligibility is unresolved by frozen sources.']
    PLAN.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'cases': len(cases), 'comparisons': len(plan['comparisons']),
                      'dispositions': len(plan['requirement_dispositions'])}))


if __name__ == '__main__':
    main()
