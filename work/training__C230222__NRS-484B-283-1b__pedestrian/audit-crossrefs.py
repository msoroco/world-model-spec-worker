"""Independent exact-source and unreviewed-status audit for curb cross-references."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    result = json.loads((HERE / 'statutory-crossrefs.json').read_text())
    inventory_path = ROOT / result['frozen_inventory_path']
    inventory = json.loads(inventory_path.read_text())['laws']
    plan = json.loads((HERE / 'case-plan.json').read_text())
    road = HERE / 'native/road.xodr'
    if result['frozen_inventory_sha256'] != sha(inventory_path) or result['authored_road_sha256'] != sha(road):
        raise ValueError('Curb cross-reference source hash differs')
    if result['curb_clause_source'] != plan['source_law']['source'] or result['curb_clause_sha256'] != plan['source_law']['sha256']:
        raise ValueError('Curb exact clause binding differs')
    xml = ET.parse(road).getroot()
    if len(xml.findall('road')) != 1 or xml.findall('.//objects/object') or xml.findall('.//junction'):
        raise ValueError('Current authored road features differ')
    rows = result['crossrefs']
    if len(rows) != 7 or len({row['law_id'] for row in rows}) != 7:
        raise ValueError('Curb cross-reference set differs')
    for row in rows:
        law_id = row['law_id']
        if law_id not in plan['source_law']['text']:
            raise ValueError('Cross-reference absent from curb clause')
        record = inventory[law_id]
        if any((row['exact_text'] != record['law']['text'],
                row['source'] != record['law']['source'],
                row['original_assignment_id'] != record['original_assignment_id'],
                row['topic_ids'] != sorted(record['topics']),
                row['exact_text_sha256'] != hashlib.sha256(record['law']['text'].encode()).hexdigest())):
            raise ValueError('Frozen cross-reference content differs: ' + law_id)
        if not row['required_original_observations'] or row['current_curb_pair_proves_applicability'] or row['legal_applicability_conclusion'] is not None:
            raise ValueError('Curb cross-reference overclaims applicability')
        if row['same_cell_construction_status'] != 'pending_physical_construction_and_review':
            raise ValueError('Curb cross-reference falsely claims construction')
    if result['applicability_resolved'] or result['physical_crossref_cases_constructed'] or result['selected_crossref_cases']:
        raise ValueError('Curb statutory coverage falsely marked complete')
    return {'independent_audit': 'pass', 'exact_frozen_crossrefs': 7,
            'physical_crossref_cases_constructed': 0,
            'legal_applicability_resolved': False, 'selected_crossref_cases': 0}


if __name__ == '__main__':
    print(json.dumps(audit()))
