"""Seal source-gated fallback compatibility and recorded-only CPU receipts.

The receipts describe synthetic fixture execution. They do not select a
production case or stand in for original Native capture.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "execution-manifest.source-gated-draft.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal(compat_root: Path, saved_root: Path) -> dict:
    manifest = json.loads(MANIFEST.read_text())
    rows = []
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        kind = case_id.rsplit("__", 1)[1]
        construction_hash = entry["candidates"][0]["construction_sha256"]
        compat_path = compat_root / kind / "fallback1" / "compatibility.json"
        saved_log = saved_root / (kind + ".command.log")
        compat = json.loads(compat_path.read_text())
        saved = json.loads(saved_log.read_text())
        if (compat.get("case_id") != case_id or compat.get("candidate_id") != "fallback1"
                or compat.get("construction_sha256") != construction_hash
                or compat.get("passed") is not True
                or "negative_case_source" not in compat.get("checks", [])):
            raise ValueError("fallback compatibility proof differs: " + case_id)
        if (saved.get("case_id") != case_id or saved.get("candidate_id") != "fallback1"
                or saved.get("passed") is not True or saved.get("recorded_only") is not True
                or saved.get("native_revision", {}).get("construction_sha256") != construction_hash
                or saved.get("analysis_revision", {}).get("runtime_manifest_sha256")
                != compat.get("runtime_manifest_sha256")):
            raise ValueError("fallback saved proof differs: " + case_id)
        folder = HERE / "cases" / kind / "fallback1"
        compat_return = folder / "current-compatibility-receipt.json"
        saved_return = folder / "saved-processing.json"
        compat_return.write_text(json.dumps(compat, indent=2, sort_keys=True) + "\n")
        saved_return.write_text(json.dumps(saved, indent=2, sort_keys=True) + "\n")
        rows.append({"case_id": case_id, "candidate_id": "fallback1",
                     "construction_sha256": construction_hash,
                     "compatibility_receipt": str(compat_return.relative_to(HERE)),
                     "compatibility_sha256": sha(compat_return),
                     "saved_receipt": str(saved_return.relative_to(HERE)),
                     "saved_sha256": sha(saved_return),
                     "positive_and_missing_source_checks": True,
                     "recorded_only": True,
                     "physical_acceptance_claimed": False})
    result = {"format": "c158208-fallback-saved-cpu-index-v1",
              "assignment_id": manifest["assignment_id"],
              "draft_manifest_sha256": sha(MANIFEST),
              "scope": "synthetic_fixture_cpu_only", "cases": rows,
              "selected_for_delivery": False, "legal_acceptance_claimed": False}
    (HERE / "deferred-fallback-saved-index.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--compat-root", type=Path, required=True)
    parser.add_argument("--saved-root", type=Path, required=True)
    args = parser.parse_args()
    outcome = seal(args.compat_root, args.saved_root)
    print(json.dumps({"cases": len(outcome["cases"]),
                      "index_sha256": sha(HERE / "deferred-fallback-saved-index.json"),
                      "scope": outcome["scope"]}, sort_keys=True))
