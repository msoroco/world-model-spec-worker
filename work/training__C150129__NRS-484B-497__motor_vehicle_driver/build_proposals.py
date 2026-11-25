"""Build exact one-way permission comparison requests without legal labels."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
CASES = (('witness_1', True, 'witness_comparison'),
         ('witness_2', False, 'witness_comparison'),
         ('exception_1_1', False, 'exception_1_comparison'),
         ('exception_1_2', True, 'exception_1_comparison'))


def main():
    entries = []
    for suffix, permission, pair in CASES:
        construction = json.loads((HERE / 'draft-permission' / suffix / 'primary/construction.json').read_text())
        entries.append({'case_id': ASSIGNMENT + '__' + suffix,
                        'target_law_id': 'NRS-484B-497',
                        'target_type': 'boundary_probe',
                        'rationale': 'Request left-side parking with or without an inventoried permission device; official authority and actual motion require review.',
                        'paired_probe_id': ASSIGNMENT + '__' + pair,
                        'deliberate_differences': ['requested_left_parking_permission_device'],
                        'probe': {'primary_variable': 'requested_left_parking_permission_device',
                                  'comparison_or_standard': 'same laned one-way road and left parking maneuver, device request differs',
                                  'target_value_or_branch': suffix},
                        'variable_assignments': {
                            'requested_left_parking_permission_device': {
                                'kind': 'controller', 'value': permission, 'unit': 'boolean'},
                            'observed_official_governing_permission': {
                                'kind': 'subject_behavior', 'value': None, 'unit': 'boolean'}},
                        'recording_description': construction['recording_description'],
                        'unresolved_judgment_calls': ['Official status, erection, governance and legal conclusion need original sources']})
    path = HERE / 'proposals' / 'cases.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({'cell_id': 'C150129', 'actor': 'motor_vehicle_driver',
                                'status': 'draft', 'sweep_specs': [], 'sweeps_expanded': True,
                                'cases': entries}, indent=2) + '\n')
    print(json.dumps({'proposal_cases': len(entries)}))


if __name__ == '__main__':
    main()
