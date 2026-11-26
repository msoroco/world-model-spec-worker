"""Bind the reviewed law and five exact City-space comparisons to delivery."""

import json
from pathlib import Path

from build_constructions import description
from city_space import CASES
from source_packet import ASSIGNMENT

ROOT = Path(__file__).resolve().parent
SOURCE = 'inputs/' + ASSIGNMENT + '/assignment.json'
SOURCE_SHA = '71e3d83fdb5d04a30b3ecc6fef14be5bcdf155a92e69e84bef8a62f92ebba8f2'


def write():
    path = ROOT / 'case-plan.json'
    plan = json.loads(path.read_text())
    ids = [ASSIGNMENT + '__' + case.name for case in CASES]
    gap = {'id': 'no-accepted-city-space-evidence',
           'requirement': 'Council-designated and duly posted City-vehicle parking space, status and parking footprint',
           'source': {'path': SOURCE, 'sha256': SOURCE_SHA},
           'why_existing_insufficient': 'Frozen accepted recording inventory is empty.'}
    plan['evidence_review']['gaps'] = [gap]
    plan['source_observation_mapping'] = {}
    plan['requirement_dispositions'] = [{
        'requirement': 'LVMC-11-52-340',
        'source': {'path': SOURCE, 'sha256': SOURCE_SHA},
        'status': 'selected_required',
        'evidence_or_gap': 'No accepted exact evidence; five source-gated delivery cases test the operative conditions.',
        'case_ids': ids}]
    channels = description()['channels']
    plan['observations'] = [{
        'name': row['name'], 'mandatory': True, 'method': row['method'],
        'source': 'original Native 900-frame City-space source, reviewed authority and four cameras'}
        for row in channels]
    for item in plan['cases']:
        item['kind'] = 'delivery'
        item['new_capture_selected'] = True
        item['gap_ids'] = [gap['id']]
        item['saved_measurement'] = 'analysis.py measure_city_space from original-city-space.jsonl and city-space-context.json'
        item['physical_acceptance_claimed'] = False
        item['physical_risk'] = {'status': 'physical',
                                 'reason': 'The official device face and parked vehicle footprint may not both be visible from the primary four-view layout.'}
    for index, item in enumerate(plan['comparisons']):
        item['comparison_id'] = ('vehicle_status', 'council_designation',
                                 'official_posting', 'governed_space_occupancy')[index]
        item['status'] = 'original_comparison_pending'
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 45,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'City parking space, street and complete vehicle',
             'interval': 'all 45 seconds'},
            {'view': 'approach', 'subject': 'vehicle approach and complete parking interval',
             'interval': 'all 45 seconds'},
            {'view': 'reference_corner', 'subject': 'official device face and governed-space bounds',
             'interval': 'all 45 seconds'},
            {'view': 'driver_reference', 'subject': 'parked vehicle and operator identity',
             'interval': 'all 45 seconds'}]}
    plan['planning_status'] = 'selected_city_space_delivery_cpu_proofs_in_progress'
    path.write_text(json.dumps(plan, indent=2) + '\n')


if __name__ == '__main__':
    write()
