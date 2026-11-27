"""Bind the same-cell return pair as draft exact cases, without readiness claim."""

import copy
import hashlib
import json
from pathlib import Path

from build_entry_return import AID, POLICIES, ROOT


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def bind():
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    ids = [AID + '__' + policy for policy in POLICIES]
    entry = plan['requirement_dispositions'][2]
    if entry['requirement'] != 'roadway-entry-yield':
        raise ValueError('Original roadway-entry disposition changed')
    entry['status'] = 'selected_required'
    entry['case_ids'] = ids
    entry['evidence_or_gap'] = (
        'Two draft same-cell road-exit-then-return constructions add a separate '
        'approaching roadway vehicle and vary only the requested pre-entry dwell. '
        'Original Native movement, pixel visibility and legal yield remain unverified.')
    plan['requirement_dispositions'][0]['case_ids'] = list(dict.fromkeys(
        plan['requirement_dispositions'][0]['case_ids'] + ids))
    baseline = copy.deepcopy(plan['cases'][0])
    for policy, case_id in zip(POLICIES, ids):
        row = copy.deepcopy(baseline)
        row.update({
            'case_id': case_id,
            'planning_status': 'unverified_definition',
            'comparison_variable': 'roadway_entry_yield_dwell',
            'comparison_unit': 'category',
            'requested_setting': policy,
            'recorded_value': None,
            'case_description': (
                'Residence-district driver first exits roadway across sidewalk '
                'into private driveway, dwells, then returns across that sidewalk '
                'to the roadway with a separate approaching vehicle.'),
            'fixed_context': (
                'Hold authored road, driveway, district, sidewalk, pedestrian, '
                'approaching-vehicle trajectory, actor and 60 s camera profile '
                'fixed; vary only requested pre-entry dwell. Preserve observed '
                'Native outcome and legal necessity as unknown.'),
            'source_topic_ids': ['text-0'],
            'selected': False,
        })
        if not any(item['case_id'] == case_id for item in plan['cases']):
            plan['cases'].append(row)
    comparison_id = AID + '__roadway_entry_yield_comparison'
    comparison = {
        'comparison_id': comparison_id, 'case_ids': ids,
        'deliberate_differences': ['roadway_entry_yield_dwell'],
        'fixed_conditions': [
            'same authored road and driveway', 'same residence district',
            'same sidewalk and pedestrian',
            'same approaching vehicle actor and trajectory',
            'same road-exit phase', 'same 60 s four-camera capture profile',
        ],
        'status': 'planned_unverified',
        'measurement_method': (
            'Compare original frame-joined ego body and speed at the roadway '
            'boundary with the approaching vehicle trajectory; report measured '
            'spacing and timing without a legal yield cutoff.'),
    }
    if not any(x['comparison_id'] == comparison_id for x in plan['comparisons']):
        plan['comparisons'].append(comparison)
    write(plan_path, plan)

    proposal_path = ROOT / 'proposals/cases.json'
    proposal = json.loads(proposal_path.read_text())
    template = copy.deepcopy(next(c for c in proposal['cases']
                                  if c['case_id'] == AID + '__stop_before_sidewalk'))
    for policy, case_id in zip(POLICIES, ids):
        construction = json.loads((ROOT / 'native/entry_return' / policy /
                                   'construction.json').read_text())
        row = copy.deepcopy(template)
        row['case_id'] = case_id
        row['rationale'] = (
            'Same-cell road-exit then roadway-return controller attempt; '
            'no physical or legal yield judgment is assigned.')
        row['recording_description'] = construction['recording_description']
        row['paired_probe_id'] = AID + '__roadway_entry_yield_pair'
        row['deliberate_differences'] = ['commanded_roadway_entry_policy']
        row['probe'] = {
            'primary_variable': 'commanded_roadway_entry_policy',
            'comparison_or_standard':
                'same road, driveway, traffic and 60 s four-camera profile',
            'target_value_or_branch': policy,
        }
        row['variable_assignments']['roadway_traffic_context']['value'] = (
            'separate approaching vehicle on same road lane with fixed trajectory')
        row['variable_assignments']['commanded_turn_path']['value'] = (
            'road-to-driveway then driveway-to-roadway')
        row['variable_assignments']['commanded_roadway_entry_policy'] = {
            'kind': 'controller', 'value': policy, 'unit': 'category'}
        for index, item in enumerate(proposal['cases']):
            if item['case_id'] == case_id:
                proposal['cases'][index] = row
                break
        else:
            proposal['cases'].append(row)
    write(proposal_path, proposal)
    index_path = ROOT / 'proposals/semantic-index.json'
    index = json.loads(index_path.read_text())
    index['stages']['cases']['sha256'] = sha(proposal_path)
    write(index_path, index)
    return {'case_ids': ids, 'comparison_id': comparison_id,
            'case_plan_sha256': sha(plan_path),
            'proposal_sha256': sha(proposal_path),
            'selected_cases': sum(bool(c.get('selected')) for c in plan['cases'])}


if __name__ == '__main__':
    print(json.dumps(bind()))
