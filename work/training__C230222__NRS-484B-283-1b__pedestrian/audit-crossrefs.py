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
        if law_id in ('NRS-484B-287-1c', 'NRS-484B-287-1d', 'NRS-484B-287-1e'):
            if row['same_cell_construction_status'] != 'selected_road_source_excludes_intersection_device_pending_original_native_review':
                raise ValueError('287 selected-road source review status differs')
            if row.get('source_eligibility_review') != 'crossref-287-eligibility-proof.json':
                raise ValueError('287 eligibility proof path differs')
            proof = json.loads((HERE / row['source_eligibility_review']).read_text())
            if (proof['pedestrian_candidate_cell_count'] != 0 or
                proof['selected_manifest_sha256'] != sha(HERE / 'execution-manifest.json') or
                not proof['changed_device_negative_control_detected'] or
                not proof['changed_crosswalk_negative_control_detected'] or
                not proof['changed_junction_negative_control_detected'] or
                proof['additional_binding_proposed'] or proof['capability_blocked_claim'] or
                proof['legal_applicability_conclusion'] is not None):
                raise ValueError('287 eligibility proof scope differs')
            fact = next(item for item in proof['crossrefs'] if item['law_id'] == law_id)
            if (fact['exact_text_sha256'] != row['exact_text_sha256'] or
                fact['original_assignment_id'] != row['original_assignment_id'] or
                fact['c230222_selected_road_has_required_intersection_device_context'] or
                fact['new_pedestrian_binding_eligible_in_frozen_catalog'] or
                fact['required_original_observations'] != row['required_original_observations'] or
                fact['same_cell_positive_variant_status'] != 'unbuilt_pending_frozen_cell_compatibility_review'):
                raise ValueError('287 source or cell fact differs')
        elif law_id == 'LVMC-11-30-060-A':
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
        elif law_id == 'LVMC-11-30-060-B':
            if row['same_cell_construction_status'] != 'authored_overhead_survey_target_600_frame_offline_public_positive_negative_saved_unselected':
                raise ValueError('Overhead survey target construction status differs')
            if row.get('cpu_construction_summary') != 'crossref-060b-native/proof.json':
                raise ValueError('Overhead survey target proof path differs')
            proof = json.loads((HERE / row['cpu_construction_summary']).read_text())
            if (len(proof['records']) != 2 or proof['original_native_visibility_verified'] or
                proof['pedestrian_tunnel_or_overhead_provided_verified'] or
                proof['legal_applicability_conclusion'] is not None):
                raise ValueError('Overhead survey target physical scope differs')
            for record in proof['records']:
                label = record['case_id'].split('__crossref_lvmc_11_30_060_b_', 1)[1]
                folder = HERE / 'crossref-060b-native' / label
                if record['construction_sha256'] != sha(folder / 'construction.json') or record['source_measurement_sha256'] != sha(folder / 'source-measurement.json'):
                    raise ValueError('Overhead construction or source measurement differs')
                for candidate, hashes in record['current_runtime_proof_hashes'].items():
                    target = (folder if candidate == 'primary' else HERE / 'crossref-060b-fallback1' / label) / 'proofs'
                    for name, digest in hashes.items():
                        if sha(target / name) != digest:
                            raise ValueError('Overhead current-runtime proof differs')
        elif law_id == 'LVMC-11-30-140-B':
            if row['same_cell_construction_status'] != 'cane_prop_survey_600_frame_offline_public_positive_negative_saved_unselected':
                raise ValueError('Cane prop survey status differs')
            if row.get('cpu_construction_summary') != 'crossref-140b-native/proof.json':
                raise ValueError('Cane prop proof path differs')
            proof = json.loads((HERE / row['cpu_construction_summary']).read_text())
            if (len(proof['records']) != 2 or proof['original_cane_pixels_verified'] or
                proof['pedestrian_blindness_verified'] or proof['driver_precautions_reviewed'] or
                proof['legal_applicability_conclusion'] is not None):
                raise ValueError('Cane prop proof scope differs')
            for record in proof['records']:
                label = record['case_id'].split('__crossref_lvmc_11_30_140_b_', 1)[1]
                folder = HERE / 'crossref-140b-native' / label
                if record['construction_sha256'] != sha(folder / 'construction.json'):
                    raise ValueError('Cane prop construction differs')
                for candidate, hashes in record['current_runtime_proof_hashes'].items():
                    target = (folder if candidate == 'primary' else HERE / 'crossref-140b-fallback1' / label) / 'proofs'
                    for name, digest in hashes.items():
                        if sha(target / name) != digest:
                            raise ValueError('Cane prop current-runtime proof differs')
        elif law_id == 'LVMC-11-46-030':
            if row['same_cell_construction_status'] != 'school_lane_warning_survey_600_frame_offline_public_positive_negative_saved_unselected':
                raise ValueError('School warning survey status differs')
            if row.get('cpu_construction_summary') != 'crossref-46-native/proof.json':
                raise ValueError('School warning proof path differs')
            proof = json.loads((HERE / row['cpu_construction_summary']).read_text())
            if (len(proof['records']) != 2 or proof['original_school_warning_pixels_verified'] or
                proof['child_context_verified'] or proof['fifty_foot_stop_and_release_verified'] or
                proof['legal_applicability_conclusion'] is not None):
                raise ValueError('School warning proof scope differs')
            for record in proof['records']:
                label = record['case_id'].split('__crossref_lvmc_11_46_030_', 1)[1]
                folder = HERE / 'crossref-46-native' / label
                if record['construction_sha256'] != sha(folder / 'construction.json'):
                    raise ValueError('School warning construction differs')
                for candidate, hashes in record['current_runtime_proof_hashes'].items():
                    target = (folder if candidate == 'primary' else HERE / 'crossref-46-fallback1' / label) / 'proofs'
                    for name, digest in hashes.items():
                        if sha(target / name) != digest:
                            raise ValueError('School warning current-runtime proof differs')
        elif row['same_cell_construction_status'] != 'pending_physical_construction_and_review':
            raise ValueError('Curb cross-reference construction status differs')
    if (result['applicability_resolved'] or result['physical_crossref_cases_constructed'] != 2 or
        result.get('authored_overhead_survey_target_cases_constructed') != 2 or
        result.get('cane_prop_survey_cases_constructed') != 2 or
        result.get('school_warning_survey_cases_constructed') != 2 or result['selected_crossref_cases']):
        raise ValueError('Curb statutory coverage falsely marked complete')
    return {'independent_audit': 'pass', 'exact_frozen_crossrefs': 7,
            'physical_crossref_cases_constructed': 2,
            'legal_applicability_resolved': False, 'selected_crossref_cases': 0}


if __name__ == '__main__':
    print(json.dumps(audit()))
