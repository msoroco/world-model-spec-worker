"""Bind the exact parking requirement, source gap, camera plan and finalizer."""
from __future__ import annotations

import json
from pathlib import Path

from author_bundles import CHANNELS

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
SOURCE = 'inputs/' + AID + '/assignment.json'
KEY = 'highway_side_two_vehicle_halt_and_exception_context'


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def main():
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    ids = [item['case_id'] for item in plan['cases']]
    plan['requirement_dispositions'] = [{
        'requirement': 'NRS-484B-450-1l highway side of a vehicle stopped or parked at highway edge or curb; stop, stand, park and each stated exception',
        'source': SOURCE, 'status': 'selected_required',
        'evidence_or_gap': 'No accepted original recording; eight exact captures and seven controlled comparisons required.',
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
            {'view': 'overview', 'subject': 'narrow highway, edge vehicle and ego',
             'interval': 'approach through terminal halt'},
            {'view': 'approach', 'subject': 'ego approach and edge vehicle',
             'interval': 'approach through terminal halt'},
            {'view': 'reference_corner', 'subject': 'curb edge and two vehicle bodies',
             'interval': 'approach through terminal halt'},
            {'view': 'driver_reference', 'subject': 'ego highway-side approach and halt',
             'interval': 'approach through terminal halt'}]}
    plan['runtime_uncertainties'] = [
        'Original highway, curb and side-by-side vehicle placement require local physical review.',
        'Stop, stand or park activity and exceptions require independent source and legal review.']
    plan['planning_status'] = 'selected_cpu_package_in_progress'
    write(plan_path, plan)
    contract = {
        'format': 'worker-measurement-contract',
        'requirements': [{
            'disposition_index': 0,
            'requirement': plan['requirement_dispositions'][0]['requirement'],
            'source': SOURCE, 'output_key': KEY, 'method': 'analyze',
            'value_type': 'object', 'kind': 'measured',
            'inputs': ['parking-history.jsonl', 'parking-site.json',
                       'trace.jsonl', 'video_frames.jsonl']}],
        'negative': {'remove': ['parking-site.json'],
                     'error_contains': 'Missing required source: parking-site.json'}}
    write(ROOT / 'measurement-contract.json', contract)


if __name__ == '__main__':
    main()
