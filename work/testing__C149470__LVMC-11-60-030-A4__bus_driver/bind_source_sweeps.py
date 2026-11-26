"""Bind selected engineering grid points without assigning legal labels."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREFIX = HERE.name + '__'


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def main():
    proposal = json.loads((HERE / 'proposals/cases.json').read_text())
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    base = next(item for item in plan['cases'] if item['case_id'] == PREFIX + 'bus_stop_below')
    planned = {item['case_id'] for item in plan['cases']}
    for selected in proposal['cases']:
        if selected.get('target_type') != 'judgment_sweep':
            continue
        cid = selected['case_id']
        if cid in planned:
            continue
        variable = selected['probe']['primary_variable']
        value = selected['sweep_point'][variable]
        entry = dict(base)
        entry['case_id'] = cid
        entry['construction'] = 'bus_curb.construct: reviewed non-tour bus at designated public-street loading place; exact engineering route request and separate traffic actor'
        entry['measurement'] = 'bus_curb.measure_original: 900 original frames; stopped right-front-wheel distance, bus-curb angle, separate traffic speed, loading actor state and source joins'
        entry['physical_risk'] = 'Requested route geometry, stopped bus orientation and other traffic movement require original Native review'
        entry['engineering_request'] = {variable: value}
        entry['legal_judgment'] = 'approximately parallel and unduly impede unresolved; engineering point is not a legal cutoff'
        plan['cases'].append(entry)
        planned.add(cid)
        plan['requirement_dispositions'][0]['case_ids'].append(cid)
    for name, left, right, variable in (
        ('parallel_engineering_grid', 'parallel_source_review-0000',
         'parallel_source_review-0002', 'heading_request_deg'),
        ('traffic_engineering_grid', 'traffic_impediment_source_review-0000',
         'traffic_impediment_source_review-0002', 'traffic_lateral_request_m')):
        if any(item['comparison_id'] == name for item in plan['comparisons']):
            continue
        plan['comparisons'].append({
            'comparison_id': name,
            'case_ids': [PREFIX + left, PREFIX + right],
            'fixed_conditions': 'same reviewed public street, curb, bus class, loading activity, camera profile and duration; vary only declared route geometry request',
            'deliberate_differences': [variable + ' engineering request; compare original observed bus-curb angle or traffic speed without a legal verdict']})
    plan['planning_status'] = 'complete_source_gated_engineering_sweeps'
    write(plan_path, plan)
    print('selected cases:', len(plan['cases']), 'comparisons:', len(plan['comparisons']))


if __name__ == '__main__':
    main()
