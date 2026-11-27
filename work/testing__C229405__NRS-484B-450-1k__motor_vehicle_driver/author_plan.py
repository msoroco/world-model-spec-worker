"""Bind exact statutory requirement, camera plan and measurement contract."""
from __future__ import annotations

import json
from pathlib import Path

from author_bundles import CHANNELS
from excavation_park import CASES

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
LAW = 'NRS-484B-450-1k'
SOURCE = 'inputs/' + AID + '/assignment.json'
KEY = 'excavation_body_passage_and_exception_context'


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def main():
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    existing = {item['case_id'] for item in plan['cases']}
    baseline = plan['cases'][0]
    for case in CASES:
        cid = AID + '__' + case.case_id
        if cid in existing:
            continue
        item = dict(baseline)
        item.update(case_id=cid, relation=case.relation,
                    halt_activity=case.activity, passage_probe=case.passage,
                    exception_context=case.exception,
                    physical_risk='Native terminal halt and passage readback require original review; no legal obstruction cutoff selected')
        plan['cases'].append(item)
    comparison_ids = {item['comparison_id'] for item in plan['comparisons']}
    additions = (
        ('park_vs_ordinary_stop', 'alongside_park_narrow', 'alongside_stop_ordinary',
         'halt activity only'),
        ('park_vs_ordinary_stand', 'alongside_park_narrow', 'alongside_stand_ordinary',
         'halt activity only'),
        ('ordinary_stop_vs_conflict_stop', 'alongside_stop_ordinary',
         'alongside_stop_conflict', 'conflict-avoidance necessity context only'),
        ('ordinary_stand_vs_officer_stand', 'alongside_stand_ordinary',
         'alongside_stand_officer', 'officer direction context only'))
    for name, first, second, difference in additions:
        if name in comparison_ids:
            continue
        plan['comparisons'].append({
            'comparison_id': name,
            'case_ids': [AID + '__' + first, AID + '__' + second],
            'fixed_conditions': 'same highway, excavation, relation, passage, vehicle, traffic actor, camera plan and duration',
            'deliberate_differences': [difference]})
    ids = [item['case_id'] for item in plan['cases']]
    plan['requirement_dispositions'] = [{
        'requirement': 'NRS-484B-450-1k highway excavation alongside/opposite halt, traffic obstruction and each stated exception',
        'source': SOURCE, 'status': 'selected_required',
        'evidence_or_gap': 'No accepted original recording; seven source-gated exact captures and controlled comparisons required.',
        'case_ids': ids}]
    plan['source_observation_mapping'] = {}
    plan['observations'] = [
        {'name': name, 'mandatory': True,
         'description': 'Original source-bound ' + name.replace('_', ' ')}
        for name in CHANNELS]
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 45,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'excavation, ego and passing traffic',
             'interval': 'approach through terminal halt'},
            {'view': 'approach', 'subject': 'ego halt route and passing traffic route',
             'interval': 'approach through terminal halt'},
            {'view': 'reference_corner', 'subject': 'excavation edge, ego body and passage',
             'interval': 'approach through terminal halt'},
            {'view': 'driver_reference', 'subject': 'ego roadwork approach and halt',
             'interval': 'approach through terminal halt'}]}
    plan['runtime_uncertainties'] = [
        'Original CARLA excavation feature and marker visibility require local physical review.',
        'Observed obstruction and stated exception applicability require independent legal review.']
    plan['planning_status'] = 'selected_cpu_package_in_progress'
    write(plan_path, plan)
    contract = {
        'format': 'worker-measurement-contract',
        'requirements': [{
            'disposition_index': 0,
            'requirement': plan['requirement_dispositions'][0]['requirement'],
            'source': SOURCE, 'output_key': KEY, 'method': 'analyze',
            'value_type': 'object', 'kind': 'measured',
            'inputs': ['excavation-history.jsonl', 'excavation-site.json',
                       'trace.jsonl', 'video_frames.jsonl']}],
        'negative': {'remove': ['excavation-site.json'],
                     'error_contains': 'Missing required source: excavation-site.json'}}
    write(ROOT / 'measurement-contract.json', contract)


if __name__ == '__main__':
    main()
