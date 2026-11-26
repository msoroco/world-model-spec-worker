"""Draft the canonical case stage without asserting statutory outcomes."""
from __future__ import annotations

import json
from pathlib import Path

from fire_lane import CASES

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / 'case-plan.json').read_text())
RECORDING = json.loads((ROOT / 'construction.json').read_text())['recording_description']


def assignments(case):
    return {
        'activity': {'kind': 'controller', 'value': case.activity,
                     'note': 'requested activity; original state must be measured'},
        'attended': {'kind': 'world_setup', 'value': case.attended,
                     'note': 'requested attendance; original observation required'},
        'property_kind': {'kind': 'world_setup', 'value': case.property_kind,
                          'note': 'requires reviewed parcel source'},
        'target_region': {'kind': 'controller', 'value': case.target_region,
                          'note': 'requested target; original body position required'},
        'exception': {'kind': 'world_setup', 'value': case.exception,
                      'note': 'requires independent original traffic or direction source'},
        'conflict_gap_m': {'kind': 'controller',
                           'value': case.sweep_setpoint_m if case.sweep_kind == 'conflict_gap' else None,
                           'note': 'requested actor gap; original gap measured separately'},
        'posted_offset_m': {'kind': 'controller',
                            'value': case.sweep_setpoint_m if case.sweep_kind == 'posted_offset' else None,
                            'note': 'requested body-centre offset; original offset measured separately'},
    }


def build():
    baseline_case = CASES[0]
    rows = [{
        'case_id': ROOT.name + '__baseline', 'target_law_id': None,
        'target_type': 'baseline',
        'rationale': 'Shared source-reviewed one-way curb and sign context; no outcome label.',
        'variable_assignments': assignments(baseline_case),
        'unresolved_judgment_calls': [],
        'recording_description': RECORDING,
    }]
    pairs = {case_id: comparison['comparison_id']
             for comparison in PLAN['comparisons']
             for case_id in comparison['case_ids']}
    for case in CASES:
        if case.sweep_kind != 'none':
            continue
        case_id = ROOT.name + '__' + case.id
        row = next(row for row in PLAN['cases'] if row['case_id'] == case_id)
        difference = next((comparison['deliberate_differences'][0]
            for comparison in PLAN['comparisons']
            if case_id in comparison['case_ids']), 'activity')
        rows.append({
            'case_id': case_id, 'target_law_id': PLAN['law_id'],
            'target_type': 'boundary_probe',
            'rationale': 'Original source-gated fire-lane observation of ' + case.id.replace('_', ' ') +
                         '; no legal classification is presumed.',
            'variable_assignments': assignments(case),
            'unresolved_judgment_calls': [
                'necessary to avoid conflict with other traffic',
                'designated and posted as a fire lane pursuant to the City\'s Fire Code'],
            'paired_probe_id': pairs.get(case_id, case.id),
            'deliberate_differences': [difference],
            'probe': {'primary_variable': difference,
                      'comparison_or_standard': 'same reviewed site and original observations',
                      'target_value_or_branch': getattr(case, difference)},
            'recording_description': RECORDING,
        })
    proposal = {'cell_id': PLAN['cell_id'], 'actor': PLAN['actor'],
                'status': 'draft', 'sweep_specs': [], 'cases': rows,
                'semantic_status': 'partial_pending_template_and_judgment_source_review'}
    destination = ROOT / 'proposals/cases.json'
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(proposal, indent=2, sort_keys=True) + '\n')
    return proposal


if __name__ == '__main__':
    print('draft canonical cases:', len(build()['cases']))
