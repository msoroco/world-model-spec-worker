"""Independent fixed-condition checks for the three C24753 exact comparisons."""
from __future__ import annotations
import json
from pathlib import Path

from delivery_audit import audit_sources

PAIRS = {
    'heavy_approach_speed': ('east_cautious_proxy','east_faster_proxy','target_speed_mps'),
    'crossing_context': ('east_cautious_proxy','east_no_crossing','crossing_vehicle'),
    'approach_direction': ('east_cautious_proxy','west_cautious_proxy','direction'),
}

def audit_pair(comparison_id, first, second, first_report, second_report):
    if comparison_id not in PAIRS:
        raise ValueError('Unknown frozen heavy comparison')
    expected_a, expected_b, variable = PAIRS[comparison_id]
    roots = [Path(first),Path(second)]
    configs = [json.loads((root/'config.json').read_text()) for root in roots]
    if [c.get('case_branch') for c in configs] != [expected_a,expected_b]:
        raise ValueError('Wrong exact comparison cases')
    reports = [audit_sources(root,report) for root,report in
               zip(roots,(first_report,second_report))]
    contexts = [json.loads((root/'signal_context.json').read_text()) for root in roots]
    for key in ('cell_id','law_id','actor','rate_hz','frames','duration_s',
                'camera_names','cameras','heavy_blueprint_id','flash_period_s'):
        if configs[0].get(key) != configs[1].get(key):
            raise ValueError('Fixed configuration differs: '+key)
    for key in ('junction_id','official_control_source','heavy_blueprint_id'):
        if contexts[0].get(key) != contexts[1].get(key):
            raise ValueError('Fixed original context differs: '+key)
    if variable != 'direction':
        for key in ('selected_direction','opendrive_id','light_actor_id'):
            if contexts[0].get(key) != contexts[1].get(key):
                raise ValueError('Fixed governed signal differs: '+key)
    else:
        if (contexts[0].get('selected_direction') == contexts[1].get('selected_direction') or
            contexts[0].get('light_actor_id') == contexts[1].get('light_actor_id')):
            raise ValueError('Opposing direction did not select a distinct signal head')
    if variable != 'target_speed_mps' and configs[0]['target_speed_mps'] != configs[1]['target_speed_mps']:
        raise ValueError('Undeclared speed change')
    if variable == 'target_speed_mps':
        if (configs[0]['target_speed_mps'] == configs[1]['target_speed_mps'] or
            reports[0]['speed_samples_mps'] == reports[1]['speed_samples_mps']):
            raise ValueError('Declared speed difference absent from original sources')
    if variable != 'crossing_vehicle' and reports[0]['crossing_present'] != reports[1]['crossing_present']:
        raise ValueError('Undeclared crossing change')
    if variable == 'crossing_vehicle' and reports[0]['crossing_present'] == reports[1]['crossing_present']:
        raise ValueError('Declared crossing difference absent from original sources')
    if variable != 'direction' and reports[0]['direction'] != reports[1]['direction']:
        raise ValueError('Undeclared direction change')
    return {'format':'worker-heavy-signal-comparison-audit',
            'comparison_id':comparison_id,'case_ids':[r['case_id'] for r in reports],
            'declared_difference':variable,'fixed_conditions_checked':True,
            'source_hashes':[r['source_hashes'] for r in reports],
            'legal_caution_judgment':'unresolved','physical_acceptance_claimed':False}
