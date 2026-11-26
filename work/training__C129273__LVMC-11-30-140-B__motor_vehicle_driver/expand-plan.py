"""Expand the frozen driver/travel cell into source-specific controlled attempts."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / 'case-plan.json'
ASSIGNMENT = HERE.name
BASE = ASSIGNMENT + '__'
NEW = {
    'white_wholly': ('white cane, wholly blind person; controlled full stop',
                     'cane_marker_form', 'white_cane', 'wholly', 'stop_clear'),
    'white_partial': ('white cane, partially blind person; controlled full stop',
                     'blindness_extent', 'white_cane', 'partially', 'stop_clear'),
    'assisted': ('person assisted by another person; controlled full stop',
                 'assistance_form', 'assisted_person', 'wholly', 'stop_clear'),
    'early_release': ('red-tipped white cane; stop then early release toward conflict',
                      'post_stop_precautions', 'white_red_tipped_cane', 'wholly', 'early_release'),
}


def main():
    plan = json.loads(PLAN.read_text())
    baseline = BASE + 'probe_1'
    for existing in plan['cases']:
        suffix = existing['case_id'].rsplit('__', 1)[-1]
        existing['kind'] = 'delivery'
        existing['target_type'] = 'controlled_attempt'
        existing['source_context_request'] = {
            'cane_or_assistance': 'white_red_tipped_cane',
            'blindness_extent': 'wholly',
            'driver_behavior': 'stop_clear' if suffix == 'probe_1' else 'no_stop',
        }
    for suffix, (target, variable, marker, blindness, behavior) in NEW.items():
        case = BASE + suffix
        plan['cases'].append({
            'case_id': case, 'target_law_id': 'LVMC-11-30-140-B',
            'kind': 'delivery', 'target_type': 'controlled_attempt',
            'physical_target': target, 'comparison_variable': variable,
            'source_branch': 'Driver approaches blind person with a source-specified cane or assistant',
            'requested_not_measured': True, 'selection_targets': ['full-train'],
            'source_context_request': {'cane_or_assistance': marker,
                                       'blindness_extent': blindness,
                                       'driver_behavior': behavior},
        })
    comparisons = [
        ('stop', 'probe_1', 'probe_2', 'full_stop_before_proceeding'),
        ('cane', 'probe_1', 'white_wholly', 'cane_marker_form'),
        ('blindness', 'white_wholly', 'white_partial', 'blindness_extent'),
        ('assistance', 'probe_1', 'assisted', 'assistance_form'),
        ('post_stop', 'probe_1', 'early_release', 'post_stop_precautions'),
    ]
    plan['comparisons'] = [{
        'comparison_id': BASE + name,
        'case_ids': [BASE + a, BASE + b],
        'deliberate_differences': [variable],
        'fixed_conditions': ['C129273 mountain_road / travel / blind_pedestrian',
                             'same driver and pedestrian route geometry',
                             '600 frames at 20 Hz and four source cameras',
                             'source request differs only as declared'],
    } for name, a, b, variable in comparisons]
    branches = {
        'Driver approaching a blind person carrying a white walking stick tipped in red.':
            [BASE + 'probe_1', BASE + 'probe_2'],
        'partial blindness': [BASE + 'white_wholly', BASE + 'white_partial'],
        'white cane or white tipped red': [BASE + 'probe_1', BASE + 'white_wholly'],
        'assisted-by-person wording': [BASE + 'probe_1', BASE + 'assisted'],
        'post-stop injury avoidance precautions': [BASE + 'probe_1', BASE + 'early_release'],
    }
    for item in plan['requirement_dispositions']:
        item['status'] = 'selected_required'
        item['case_ids'] = branches[item['branch']]
        item['evidence_or_gap'] = ('Selected controlled Native request with source-hashed measurement; '
                                   'original blindness, marker appearance, assistance, motion, injury '
                                   'avoidance and legal judgment require later independent review.')
    plan['selected_branch'] = 'complete source-specific driver comparisons'
    plan['blockers'] = ['Original Native marker identity, blindness and assistant evidence require independent review; CPU source requests are not legal findings.']
    PLAN.write_text(json.dumps(plan, indent=2) + '\n')
    print(json.dumps({'cases': len(plan['cases']), 'comparisons': len(plan['comparisons'])}))


if __name__ == '__main__':
    main()
