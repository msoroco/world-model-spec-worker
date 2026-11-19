"""Recompute the selected lane measurements and decode all four saved cameras."""

import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import audit_attempt


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(manifest_path, versions):
    manifest = json.loads(Path(manifest_path).read_text())
    selected = {entry["case_id"]: entry for entry in manifest["cases"]}
    rows = {}
    for version in map(Path, versions):
        processing_path = version / "processing.json"
        processing = json.loads(processing_path.read_text())
        case = processing["case_id"]
        if case in rows or case not in selected:
            raise ValueError("Duplicate or unselected saved case: " + case)
        if (processing.get("passed") is not True
                or processing.get("originals_preserved") is not True
                or processing.get("missing_evidence") is not False
                or processing.get("analysis_revision", {}).get("construction_sha256")
                != selected[case]["construction_sha256"]):
            raise ValueError("Saved processing is incomplete or stale: " + case)
        stage = version / "analysis"
        if sha(stage / "construction.json") != selected[case]["construction_sha256"]:
            raise ValueError("Saved analysis selected another construction: " + case)
        source = audit_attempt(stage, stage / "analysis-report.json")
        if source["case_id"] != case or set(source["camera_decodes"]) != {
                "overview", "approach", "reference_corner", "driver_reference"}:
            raise ValueError("Original source or camera audit is incomplete: " + case)
        rows[case] = {
            "case_id": case,
            "saved_processing_sha256": sha(processing_path),
            "construction_sha256": selected[case]["construction_sha256"],
            "source_audit": source,
        }
    if set(rows) != set(selected):
        raise ValueError("Selected case source-audit coverage differs")
    return {
        "format": "worker-lane-source-audit-batch",
        "assignment_id": manifest["assignment_id"],
        "source_audit_script_sha256": sha(Path(__file__).with_name("delivery_audit.py")),
        "cases": [rows[entry["case_id"]] for entry in manifest["cases"]],
        "physical_visibility_claimed": False,
        "legal_acceptance_claimed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--version", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("Retain prior source audit")
    output.write_text(json.dumps(audit(args.manifest, args.version), indent=2) + "\n")


if __name__ == "__main__":
    main()
