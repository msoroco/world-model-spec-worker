"""Verify all four exact diagnostic contrasts without claiming Native evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from comparison_audit import audit_pair

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    data = {}
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        root = REPO / ".runtime-work/c202480-owner" / (
            "compat-inside-15-v5" if suffix == "inside_15" else "compat-" + suffix + "-positive")
        proof = json.loads((root / "compatibility.json").read_text())
        if not proof["passed"] or proof["construction_sha256"] != entry["construction_sha256"]:
            raise ValueError("comparison has stale exact-case diagnostic source")
        report = json.loads((root / "analysis-report.json").read_text())
        measured = report["measurements"]
        data[entry["case_id"]] = {
            "source_kind": "synthetic_fixture",
            "source_sha256": sha(root / "rail-stop-packet.json"),
            "crossing_map_sha256": sha(root / "native-crossing-geometry.json"),
            "crossing_authority_sha256": sha(root / "native-authority-record.json"),
            "stop_device_sha256": sha(root / "native-stop-device.json"),
            "gap_ft": measured["stop_gap"]["value"]["minimum_body_corner_gap_ft"],
            "complete_stop": measured["cessation"]["value"]["complete_stop_observed"],
            "conflict": measured["departure_context"]["value"]["conflict_actor_present"]}
    fields = {"lower_15_ft": "gap_ft", "upper_50_ft": "gap_ft",
              "cessation": "complete_stop", "subsequent_care": "conflict"}
    rows = []
    for comparison in plan["comparisons"]:
        ident = comparison["comparison_id"]
        cases = comparison["case_ids"]
        if ident not in fields or len(cases) not in (2, 3):
            raise ValueError("unexpected comparison matrix")
        selected = [data[case] for case in cases]
        for field in ("crossing_map_sha256", "crossing_authority_sha256", "stop_device_sha256"):
            if len({row[field] for row in selected}) != 1:
                raise ValueError("diagnostic fixed source differs: " + ident + " " + field)
        values = [row[fields[ident]] for row in selected]
        if len(set(values)) != len(values):
            raise ValueError("diagnostic comparison lacks declared contrast: " + ident)
        for left, right in zip(cases, cases[1:]):
            try:
                audit_pair({"case_id": left, **data[left]},
                           {"case_id": right, **data[right]},
                           {"comparison_id": ident, "case_ids": [left, right],
                            "variable": "stop_position_ft"})
            except ValueError as error:
                if str(error) != "comparison requires original saved source":
                    raise
            else:
                raise ValueError("synthetic comparison incorrectly entered production audit")
        rows.append({"comparison_id": ident, "case_ids": cases,
                     "diagnostic_measurement": fields[ident], "values": values,
                     "fixed_source_hashes": {field: selected[0][field] for field in
                                             ("crossing_map_sha256", "crossing_authority_sha256",
                                              "stop_device_sha256")},
                     "production_source_rejected": True,
                     "physical_status": "pending_original_native_capture"})
    if len(rows) != 4:
        raise ValueError("four comparison plans required")
    (HERE / "comparison-diagnostic-proof.json").write_text(json.dumps({
        "format": "rail-stop-comparison-diagnostic-proof", "comparisons": rows,
        "scope": "Synthetic contrast and production source rejection only; no Native physical or legal judgment."},
        indent=2) + "\n")
    print("four diagnostic contrasts and production-source rejections passed")


if __name__ == "__main__":
    main()
