"""Current-runtime validation of the unselected 287(c) delivery entry draft."""
import hashlib
import json
from pathlib import Path

from scenario_pipeline.worker_exchange.candidate_constructions import validate as validate_candidates
from scenario_pipeline.worker_exchange.physical_preparation import validate as validate_physical
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case
from scenario_pipeline.worker_exchange.package_compatibility import check_receipts

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
ROOT = ASSIGNMENT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    draft_path = HERE / 'delivery-entry-draft.json'
    draft = json.loads(draft_path.read_text())
    if draft['selected'] is not False or len(draft['cases']) != 2:
        raise ValueError('287(c) draft selection status differs')
    rows = []
    for entry in draft['cases']:
        validate_candidates(ASSIGNMENT, entry, 'NRS-484B-283-1b', 'C230222',
                            required=True, require_alternate=True)
        validate_physical(ROOT, ASSIGNMENT, entry)
        validate_case(ASSIGNMENT, entry, ['full-train'])
        rows.append({'case_id': entry['case_id'],
                     'construction_sha256': entry['construction_sha256'],
                     'physical_preparation_sha256': entry['physical_preparation']['sha256'],
                     'delivery_audit_sha256': entry['delivery_acceptance']['script_sha256']})
    check_receipts(ROOT, ASSIGNMENT, draft)
    proof = {'format': 'c230222-287c-unselected-delivery-entry-validation-v1',
             'draft_sha256': sha(draft_path), 'cases': rows,
             'candidate_validation': True, 'physical_preparation_validation': True,
             'delivery_handoff_validation': True, 'package_receipt_validation': True,
             'selected_for_delivery': False}
    target = HERE / 'delivery-entry-proof.json'
    target.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'cases': len(rows), 'proof_sha256': sha(target)}))


if __name__ == '__main__':
    main()
