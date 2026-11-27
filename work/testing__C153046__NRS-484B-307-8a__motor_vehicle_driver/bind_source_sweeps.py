"""Bind exact expanded engineering sweep points to the selected case plan."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> None:
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    proposal = json.loads((ROOT / 'proposals/cases.json').read_text())
    sweep_cases = [case for case in proposal['cases'] if case.get('sweep_id')]
    if len(sweep_cases) != 6 or len(proposal['sweep_specs']) != 2:
        raise ValueError('expected six exact points on two fixed engineering sweeps')
    plan['cases'] = [case for case in plan['cases'] if not case.get('sweep_id')]
    plan['comparisons'] = [row for row in plan['comparisons']
                           if not row['comparison_id'].startswith('engineering_')]
    for case in sweep_cases:
        values = {name: assignment['value'] for name, assignment in
                  case['variable_assignments'].items()
                  if name not in ('stop_reference_front_signed_distance',
                                  'directed_conflict_release_delay')}
        plan['cases'].append({
            'case_id': case['case_id'], 'target_law_id': plan['law_id'],
            'target_type': 'judgment_sweep', 'draft_variables': values,
            'sweep_id': case['sweep_id'], 'sweep_spec_version': case['sweep_spec_version'],
            'sweep_point': case['sweep_point'], 'selection_rank': case['selection_rank'],
            'physical_risk_assessment': {'status': 'unverified',
                'reason': 'Original Native stop reference, directed participant and body history require reviewed source.'},
            'preparation_status': 'source_gated_engineering_physical_grid',
            'physical_acceptance_claimed': False, 'legal_judgment': 'unresolved'})
    for name, sweep_id in (
        ('engineering_stop_margin', ROOT.name + '__stop_reference_source_review'),
        ('engineering_yield_release', ROOT.name + '__directed_yield_source_review')):
        cases = sorted((case for case in sweep_cases if case['sweep_id'] == sweep_id),
                       key=lambda case: next(iter(case['sweep_point'].values())))
        if len(cases) != 3:
            raise ValueError('fixed sweep endpoint/interior count differs')
        variable = next(iter(cases[0]['sweep_point']))
        plan['comparisons'].append({
            'comparison_id': name, 'case_ids': [cases[0]['case_id'], cases[-1]['case_id']],
            'deliberate_differences': [variable],
            'fixed_conditions': ['same exact law and source-reviewed site',
                                 'same official red signal and original-frame measurement',
                                 'controller request only; legal outcome unresolved'],
            'status': 'draft_requested_only_realized_measurement_pending',
            'realized_difference_claimed': False})
        # The sorted middle point is an independently requested construction.
        # Bind it to the same fixed baseline so every sweep point has an
        # original-source controlled pair without adding a recording.
        plan['comparisons'].append({
            'comparison_id': name + '_interior',
            'case_ids': [cases[0]['case_id'], cases[1]['case_id']],
            'deliberate_differences': [variable],
            'fixed_conditions': ['same exact law and source-reviewed site',
                                 'same official red signal and original-frame measurement',
                                 'controller request only; legal outcome unresolved'],
            'status': 'draft_requested_only_realized_measurement_pending',
            'realized_difference_claimed': False})
    plan['requirement_dispositions'][0]['case_ids'] = [case['case_id'] for case in plan['cases']]
    plan['planning_status'] = 'fourteen_selected_source_gated_engineering_grid_cases'
    plan['runtime_uncertainties'] = [
        'Exact reviewed C153046 Native site and original capture remain required for physical/legal review.',
        'Six fixed engineering sweep points are controller requests, not original measurements or legal thresholds.']
    plan_path.write_text(json.dumps(plan, indent=2) + '\n')
    print('bound', len(plan['cases']), 'selected cases and', len(plan['comparisons']), 'comparisons')


if __name__ == '__main__':
    main()
