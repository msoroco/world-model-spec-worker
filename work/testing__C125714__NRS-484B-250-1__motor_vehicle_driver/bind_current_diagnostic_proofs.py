"""Retain exact current-runtime synthetic proofs for all seven crossing cases.

This binds diagnostic software checks only. A reviewed original source packet is
still required before the nondiagnostic selected manifest can be promoted.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c125714-owner"
KINDS = ("precedence", "advance", "other_later", "opposite_straight",
         "opposite_intends_left", "opposite_makes_left", "wide_same_crossing")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def bind() -> dict:
    manifest = read(ROOT / "diagnostic-execution-manifest.json")
    by_case = {row["case_id"]: row for row in manifest["cases"]}
    exact = {ROOT.name + "__" + suffix for suffix in KINDS}
    if set(by_case) != exact or manifest.get("diagnostic_only") is not True:
        raise ValueError("seven exact diagnostic constructions required")
    physical = read(ROOT / "physical-outcome-diagnostic-proof.json")
    audited = read(ROOT / "delivery-diagnostic-audit-proof.json")
    physical_by_case = {row["case_id"]: row for row in physical["cases"]}
    audited_by_case = {row["case_id"]: row for row in audited["cases"]}
    if (set(physical_by_case) != exact or set(audited_by_case) != exact or
            len(audited["comparisons"]) != 5 or audited.get("diagnostic_only") is not True):
        raise ValueError("current seven-case physical or independent audit missing")
    rows = []
    for suffix in KINDS:
        case_id = ROOT.name + "__" + suffix
        entry = by_case[case_id]
        construction = ROOT / entry["construction"]
        if sha(construction) != entry["construction_sha256"]:
            raise ValueError("diagnostic construction hash changed: " + suffix)
        compat_dir = SCRATCH / "current-compat" / suffix
        receipt = read(compat_dir / "compatibility.json")
        saved = read(SCRATCH / ("current-saved-" + suffix + ".log"))
        offline_path = SCRATCH / ("current-offline-" + suffix) / "offline.log"
        offline = offline_path.read_text(encoding="utf-8")
        if (receipt.get("passed") is not True or receipt.get("case_id") != case_id or
                receipt.get("construction_sha256") != entry["construction_sha256"] or
                receipt.get("runtime_manifest_sha256") != manifest["runtime_manifest_sha256"] or
                saved.get("passed") is not True or saved.get("case_id") != case_id or
                saved.get("recorded_only") is not True or saved.get("originals_preserved") is not True or
                saved.get("physical_acceptance_claimed") is not False or
                '"static_construction_valid": true' not in offline):
            raise ValueError("current runtime proof failed or stale: " + suffix)
        if (physical_by_case[case_id].get("construction_sha256") != entry["construction_sha256"] or
                {item["status"] for item in physical_by_case[case_id]["fixtures"]} !=
                {"met", "not_met", "unverified"} or
                audited_by_case[case_id].get("native_provenance_rejected") is not True):
            raise ValueError("current physical or independent proof failed: " + suffix)
        folder = ROOT / "cases" / suffix
        folder.mkdir(exist_ok=True)
        sources = {"offline": offline_path,
                   "compatibility": compat_dir / "compatibility.json",
                   "compatibility_analysis": compat_dir / "compatibility-analysis.log",
                   "negative_analysis": compat_dir / "negative-analysis.log",
                   "saved_processing": SCRATCH / ("current-saved-" + suffix + ".log")}
        bindings = {}
        for key, source in sources.items():
            destination = folder / ("current-" + key.replace("_", "-") + source.suffix)
            shutil.copyfile(source, destination)
            bindings[key] = {"path": str(destination.relative_to(ROOT)),
                             "sha256": sha(destination)}
        rows.append({"case_id": case_id, "construction_sha256": entry["construction_sha256"],
                     "proofs": bindings, "physical_fixture_count": 3,
                     "independent_delivery_audit_passed": True,
                     "scope": "synthetic_software_fixture"})
    result = {"format": "c125714-current-diagnostic-proof-index",
              "assignment_id": ROOT.name, "runtime_manifest_sha256": manifest["runtime_manifest_sha256"],
              "status": "source_gated_cpu_preparation", "original_delivery_claimed": False,
              "cases": rows, "comparison_ids": sorted(row["comparison_id"] for row in audited["comparisons"]),
              "physical_proof": {"path": "physical-outcome-diagnostic-proof.json",
                                 "sha256": sha(ROOT / "physical-outcome-diagnostic-proof.json")},
              "independent_audit_proof": {"path": "delivery-diagnostic-audit-proof.json",
                                          "sha256": sha(ROOT / "delivery-diagnostic-audit-proof.json")}}
    (ROOT / "current-diagnostic-proof-index.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    result = bind()
    print(json.dumps({"cases": len(result["cases"]),
                      "comparisons": len(result["comparison_ids"]),
                      "scope": result["status"]}, sort_keys=True))
