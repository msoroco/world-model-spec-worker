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
        if law_id == 'LVMC-11-30-060-A':
            expected_status = 'authored_native_crosswalk_600_frame_offline_public_positive_negative_and_saved_unselected'
            if row['same_cell_construction_status'] != expected_status:
                raise ValueError('Crosswalk construction status differs')
            if row.get('cpu_construction_summary') != 'crossref-060a-native/proof.json':
                raise ValueError('Crosswalk proof path differs')
            proof = json.loads((HERE / row['cpu_construction_summary']).read_text())
            if (len(proof['records']) != 2 or not proof['missing_frame_rejected'] or
                proof['original_native_observed'] or proof['legal_applicability_conclusion'] is not None):
                raise ValueError('Crosswalk proof scope differs')
            for record in proof['records']:
                label = record['case_id'].rsplit('_', 1)[-1]
                if label not in ('marked', 'outside'):
                    raise ValueError('Crosswalk case identity differs')
                folder = HERE / 'crossref-060a-native' / label
                if record['construction_sha256'] != sha(folder / 'construction.json') or record['source_measurement_sha256'] != sha(folder / 'source-measurement.json'):
                    raise ValueError('Crosswalk construction or source measurement differs')
                for name, digest in record['current_runtime_proof_hashes'].items():
                    if sha(folder / 'proofs' / name) != digest:
                        raise ValueError('Crosswalk public/saved proof differs')
                fallback = HERE / 'crossref-060a-fallback1' / label
                for name, digest in record['fallback1_current_runtime_proof_hashes'].items():
                    if sha(fallback / 'proofs' / name) != digest:
                        raise ValueError('Crosswalk fallback proof differs')
        elif row['same_cell_construction_status'] != 'pending_physical_construction_and_review':
            raise ValueError('Curb cross-reference construction status differs')
    if result['applicability_resolved'] or result['physical_crossref_cases_constructed'] != 2 or result['selected_crossref_cases']:
        raise ValueError('Curb statutory coverage falsely marked complete')
    return {'independent_audit': 'pass', 'exact_frozen_crossrefs': 7,
            'physical_crossref_cases_constructed': 2,
            'legal_applicability_resolved': False, 'selected_crossref_cases': 0}


if __name__ == '__main__':
    print(json.dumps(audit()))
