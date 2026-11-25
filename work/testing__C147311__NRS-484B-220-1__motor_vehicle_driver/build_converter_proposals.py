"""Bind selected diagnostic proposals to exact frozen one-way cases."""
from __future__ import annotations

import json
from pathlib import Path

from one_way_direction import CASES

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name


def main():
    plan = json.loads((ROOT / 'case-plan.json').read_text(encoding='utf-8'))
    rows = []
    for case in CASES:
        case_id = ASSIGNMENT + '__' + case.name
        construction = ROOT / ('construction.json' if case == CASES[0] else f'cases/{case.name}/construction.json')
        description = json.loads(construction.read_text(encoding='utf-8'))['recording_description']
        rows.append({'case_id': case_id, 'target_law_id': plan['law_id'],
                     'target_type': 'boundary_probe',
                     'rationale': 'Diagnostic source-gated direction probe; original sign and motion remain unreviewed.',
                     'recording_description': description,
                     'probe': {'primary_variable': 'actual_direction',
                               'target_value_or_branch': case.direction,
                               'comparison_or_standard': 'Original velocity projection on reviewed designated direction'},
                     'variable_assignments': {
                         'selected_lane': {'kind': 'world_setup', 'unit': 'categorical',
                                           'value': case.lane},
                         'actual_direction': {'kind': 'world_setup', 'unit': 'categorical',
                                              'value': case.direction}},
                     'unresolved_judgment_calls': [],
                     'deliberate_differences': ['selected_lane', 'actual_direction']})
    out = {'format': 'worker-case-proposals', 'assignment_id': ASSIGNMENT,
           'cases': rows, 'diagnostic_only': True}
    path = ROOT / 'proposals/cases.json'
    path.write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
    print(len(rows))


if __name__ == '__main__':
    main()
