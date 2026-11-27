"""Build exact NRS 484B.267(1)(c) stop-through-passage coverage."""

import json
from pathlib import Path

from emergency_construction import CASES
from native_packet import AID

HERE = Path(__file__).resolve().parent


def build():
    path = HERE / 'case-plan.json'
    plan = json.loads(path.read_text(encoding='utf-8'))
    description = ('Original 20 Hz subject and emergency unit positions and body extents, '
                   'unit approach and passage, qualifying flashing-light use, subject complete '
                   'cessation and unchanged stopping position until passage, reviewed authority '
                   'and officer context, with four synchronized original camera views')
    cases = []
    for case in CASES:
        cases.append({
            'case_id': AID + '__' + case.suffix,
            'target_law_id': 'NRS-484B-267-1c', 'cell_id': 'C405341',
            'actor': 'motor_vehicle_driver', 'variant': case.suffix,
            'target_vehicle_request': case.unit_class,
            'flashing_light_request': case.light_request,
            'immediate_approach_request': case.immediate,
            'stop_response_request': case.stopping,
            'early_departure_request': case.early_departure,
            'officer_direction_request': 'proceed' if case.officer_direction else 'none',
            'approach_direction_request': case.direction,
            'recording_description': description,
            'planning_status': 'exact_target_unexecuted',
            'new_capture_selected': True,
            'construction_status': 'source_gated_exact_bundle',
            'gap_ids': ['no-original-1c-recording'],
        })
    plan['cases'] = cases
    baseline = cases[0]['case_id']
    changes = {
        'immediate_approach_no_stop': 'complete cessation versus continued travel',
        'early_departure': 'held position until passage versus departure before passage',
        'no_immediate_approach': 'immediate relative approach',
        'lights_inactive': 'use of qualifying flashing lights',
        'lights_unqualified': 'qualification of flashing equipment',
        'officer_directs_otherwise': 'contrary law-enforcement direction and instructed response',
        'regulatory_official_stop': 'authorized emergency versus regulatory official class',
        'same_direction_approach_stop': 'opposing versus same-direction approach',
    }
    plan['comparisons'] = [{
        'comparison_id': 'stop_remain_vs_' + case.suffix,
        'case_ids': [baseline, AID + '__' + case.suffix],
        'fixed_conditions': [
            'paved C405341 route and ordinary subject driver except declared difference',
            '20 Hz 45 s four-camera original-source protocol',
            'unit authority, equipment, lights, officer context, route and subject response except declared difference',
            'original body-extent readbacks and frame-joined passage computation',
        ],
        'deliberate_differences': [changes[case.suffix]],
        'isolated_question': changes[case.suffix], 'status': 'unexecuted',
    } for case in CASES[1:]]
    plan['requirement_dispositions'][0]['case_ids'] = [row['case_id'] for row in cases]
    plan['planning_status'] = 'exact_delivery_selected'
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return len(cases), len(plan['comparisons'])


if __name__ == '__main__':
    print(build())
