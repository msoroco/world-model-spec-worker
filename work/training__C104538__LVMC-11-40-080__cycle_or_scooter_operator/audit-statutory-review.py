"""Independent exact-clause and retained-proof binding for C104538 LVMC."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
plan = json.loads((HERE/"case-plan.json").read_text())
review = json.loads((HERE/"statutory-branch-review.json").read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert review["format"] == "c104538-lvmc-1140080-statutory-review-v1"
assert review["assignment_id"] == plan["assignment_id"]
assert review["law_id"] == plan["law_id"] == "LVMC-11-40-080"
assert review["exact_text"] == plan["source_law"]["text"]
assert hashlib.sha256(review["exact_text"].encode()).hexdigest() == review["text_sha256"]
assert review["frozen_cell"] == plan["frozen_cell"]
assert len(review["branches"]) == 2
mounted, exception = review["branches"]
assert mounted["branch_id"] == "mounted_no_u_turn_sign"
assert exception["branch_id"] == "dismount_exception"
assert mounted["exact_phrase"] in review["exact_text"]
assert exception["exact_phrase"] in review["exact_text"]
assert mounted["controlled_case_ids"] == [c["case_id"] for c in plan["cases"]]
assert mounted["status"] == "cpu_runnable_synthetic_pending_original_and_delivery"
assert exception["status"] == "pending_physical_and_legal_review"
assert not review["sign_authorization_proven"] and not review["original_native_observed"]
assert not review["selected_strict_v2_passed"] and not review["accepted"]
for name, digest in review["proof_sha256"].items():
    assert sha(HERE/name) == digest
assert json.loads((HERE/"draft-exact-offline-audit.json").read_text())["passed"]
assert json.loads((HERE/"draft-package-audit-v1.json").read_text())["passed"]
source = json.loads((HERE/"draft-native-source-manifest.json").read_text())
controls = [entry for entry in source["entries"] if entry["kind"] == "dismounted_turn"]
assert len(controls) == 4
assert all(entry["measurement"]["dismount_frame"] == 200 and
           entry["measurement"]["first_turn_frame"] > 200 for entry in controls)
receipt = {"passed":True,"scope":"exact clause and retained synthetic CPU proof binding",
    "branches":2,"mounted_cases":2,"dismount_controls":4,
    "review_sha256":sha(HERE/"statutory-branch-review.json"),
    "original_native_observed":False,"accepted":False}
(HERE/"statutory-branch-audit.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
print(json.dumps(receipt))
