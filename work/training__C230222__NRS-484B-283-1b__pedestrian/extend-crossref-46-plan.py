"""Register unselected school-warning survey pair without claiming statutory applicability."""
import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREFIX = HERE.name + '__crossref_lvmc_11_46_030_'


def main():
    path = HERE / 'case-plan.json'
    plan = json.loads(path.read_text())
    labels = ('school_warning_candidate', 'no_school_warning')
    ids = [PREFIX + label for label in labels]
    existing = {case['case_id'] for case in plan['cases']}
    template = next(case for case in plan['cases'] if case['case_id'].endswith('__crossref_lvmc_11_30_060_b_no_overhead'))
    for label, case_id in zip(labels, ids):
        if case_id in existing:
            continue
        case = copy.deepcopy(template)
        case.update(case_id=case_id,
                    kind='unselected_cpu_survey_preparation',
                    physical_target='authored school pedestrian lane and warning device survey targets, with warning state and children unverified' if label == labels[0] else 'matched curb crossing without authored school lane or warning target',
                    comparison_variable='school_warning_target_presence',
                    target_type='exception_context',
                    requested_not_measured=True)
        case['recording_description']['limitations'] = [
            'Conditional stopping assumptions are not measured driver capability',
            'Native school lane and warning pixels, active warning state, children, 50-foot stop and release signal are unverified',
            'Authored road objects are survey targets and cannot establish legal applicability']
        plan['cases'].append(case)
        plan['requirement_dispositions'][0]['case_ids'].append(case_id)
    comparison_id = HERE.name + '__crossref_lvmc_11_46_030_comparison'
    if comparison_id not in {c['comparison_id'] for c in plan['comparisons']}:
        plan['comparisons'].append({
            'comparison_id': comparison_id,
            'case_ids': ids,
            'deliberate_differences': ['school_warning_target_presence'],
            'fixed_conditions': ['frozen C230222 road/travel/curb cell and pedestrian actor',
                                 'curb and vehicle paths, controller, cameras, and 30-second duration']})
    path.write_text(json.dumps(plan, indent=2) + '\n')
    print(json.dumps({'cases': len(plan['cases']), 'comparisons': len(plan['comparisons'])}))


if __name__ == '__main__':
    main()
