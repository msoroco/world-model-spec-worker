"""Independently check six current Walk delivery receipts and rejection gates."""
import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/pipeline"))
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if len(manifest["cases"]) != 6:
        raise ValueError("Six selected cases required")
    rows = []
    rejected = 0
    for entry in manifest["cases"]:
        contract = validate_case(HERE, entry, ["full-train"])
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        diagnostic_path = HERE / f"update201-{suffix}-delivery-diagnostic.json"
        diagnostic = json.loads(diagnostic_path.read_text())
        if (diagnostic["case_id"] != entry["case_id"] or
                diagnostic["passed"] is not False or
                diagnostic["source_shaped_unit_test"] is not True or
                set(diagnostic["source_frame_counts"].values()) != {480} or
                any(diagnostic["checks"].values()) or
                diagnostic["original_physical_acceptance_claimed"] is not False):
            raise ValueError("Diagnostic delivery source differs: " + suffix)
        for field in ("script_sha256", "test_log_sha256", "negative_log_sha256"):
            changed = copy.deepcopy(entry)
            changed["delivery_acceptance"][field] = "0" * 64
            try:
                validate_case(HERE, changed, ["full-train"])
            except ValueError:
                rejected += 1
            else:
                raise ValueError("Corrupt delivery receipt accepted: " + suffix + " " + field)
        rows.append({"case_id": entry["case_id"],
                     "diagnostic_sha256": sha(diagnostic_path),
                     "positive_log_sha256": contract["test_log_sha256"],
                     "negative_log_sha256": contract["negative_log_sha256"]})
    output = HERE / "update201-delivery-independent-audit.json"
    output.write_text(json.dumps({"format": "c111256-current-delivery-independent-audit-v1",
                                  "manifest_sha256": sha(manifest_path),
                                  "selected_cases": 6, "corruptions_rejected": rejected,
                                  "accepted_originals": 0, "rows": rows}, indent=2) + "\n")
    print(json.dumps({"selected_cases": 6, "corruptions_rejected": rejected,
                      "audit_sha256": sha(output)}))


if __name__ == "__main__":
    main()
