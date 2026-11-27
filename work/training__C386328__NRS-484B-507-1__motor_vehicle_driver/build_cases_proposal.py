"""Draft five exact freight-zone cases without physical or legal verdicts."""
import json
from pathlib import Path

from build_selected import AID, CASES, config, description

HERE = Path(__file__).resolve().parent


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    by_id = {case['case_id']: case for case in plan['cases']}
    entries = []
    for slug, intent in CASES.items():
        cid = AID + '__' + slug
        item = by_id[cid]
        entries.append({'case_id': cid, 'target_law_id': 'NRS-484B-507-1',
            'target_type': 'controlled_branch_probe',
            'probe': {'primary_variable': item['comparison_variable'],
                      'comparison_or_standard': 'Source-measured freight-zone episode without legal duration cutoff',
                      'target_value_or_branch': slug},
            'paired_probe_id': 'C386328-freight-zone-branches',
            'deliberate_differences': [item['comparison_variable']],
            'rationale': 'Authored zone, sign, material, passenger and waiting-vehicle requests require original Native and independent review.',
            'recording_description': description(),
            'unresolved_judgment_calls': ['freight zone and sign authority',
                                          'actual material or passenger loading',
                                          'expeditiousness or temporary character',
                                          'materials-vehicle classification and physical interference'],
            'variable_assignments': {
                'material_activity_request': {'kind': 'controller', 'unit': 'category',
                                               'value': intent['material']},
                'passenger_activity_request': {'kind': 'controller', 'unit': 'category',
                                                'value': intent['passenger']},
                'signed_effective_hours': {'kind': 'world_setup', 'unit': 'category',
                                            'value': 'inside' if intent['effective'] else 'outside'},
                'materials_vehicle_waiting_request': {'kind': 'participant', 'unit': 'boolean',
                                                       'value': intent['waiting']}}})
    baseline = {'case_id': AID + '__baseline', 'target_law_id': None,
                'target_type': 'baseline', 'rationale': 'Unselected neutral freight curb request definition.',
                'recording_description': description(),
                'unresolved_judgment_calls': ['freight zone sign authority', 'actual activity'],
                'variable_assignments': entries[1]['variable_assignments']}
    value = {'actor': 'motor_vehicle_driver', 'cell_id': 'C386328', 'status': 'draft',
             'sweeps_expanded': True, 'cases': [baseline, *entries],
             'sweep_specs': [{'sweep_id': 'unresolved_freight_zone_judgments',
                             'target_law_id': 'NRS-484B-507-1',
                             'judgment_refs': ['expeditious', 'temporarily', 'interference'],
                             'status': 'incomplete',
                             'rationale': 'Five controlled requests expose source conditions; no original legal threshold or physical interference result is established.',
                             'missing_inputs': ['Original regulatory authority',
                                                'Independent activity/identity review',
                                                'Original spatial-temporal interference review']}]}
    path = HERE / 'proposals/cases.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'selected_cases': len(entries), 'path': str(path)}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
