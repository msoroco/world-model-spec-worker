"""Retain 24 exact-case source-bound compatibility receipts under work/."""
from __future__ import annotations

import json
from pathlib import Path

from source_join_audit import read, require, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
RUNS = ROOT / ".runtime-work/c110454-update024-six-selected"
PROOFS = HERE / "update024-selected-proofs"
OUTPUT = HERE / "update025-source-receipts"
CHECKS = {"actual_analysis", "native_validation", "mandatory_observations",
          "lean_decoder", "render", "final_decode", "acquisition_unchanged",
          "derived_outputs_rebuilt", "four_camera_sources", "selected_measurements",
          "negative_case_source"}


def export() -> dict:
    manifest = read(MANIFEST)
    require(len(manifest["cases"]) == 6, "Selected manifest case count differs")
    rows = []
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(HERE.name + "__")
        contract = read(HERE / entry["measurement_contract"])
        expected_error = contract["negative"]["error_contains"]
        for candidate in (entry, *entry["candidates"]):
            ident = candidate["id"]
            original = RUNS / suffix / ident / "compatibility"
            prior = read(PROOFS / suffix / ident / "proof.json")
            receipt = read(original / "compatibility.json")
            require(prior["manifest_sha256"] == sha(MANIFEST) and
                    prior["construction_sha256"] == candidate["construction_sha256"] and
                    prior["compatibility_log_sha256"] == sha(PROOFS / suffix / ident / "compatibility.log") and
                    receipt.get("case_id") == case and receipt.get("candidate_id") == ident and
                    receipt.get("construction_sha256") == candidate["construction_sha256"] and
                    receipt.get("runtime_manifest_sha256") == manifest["runtime_manifest_sha256"] and
                    receipt.get("passed") is True and CHECKS <= set(receipt.get("checks", [])) and
                    receipt.get("scope") == "diagnostic software compatibility only" and
                    receipt.get("log_sha256") == sha(original / "compatibility-analysis.log") and
                    receipt.get("negative_log_sha256") == sha(original / "negative-analysis.log") and
                    receipt.get("negative_error_contains") == expected_error and
                    expected_error in (original / "negative-analysis.log").read_text(),
                    "Selected compatibility receipt/source differs: " + suffix + "/" + ident)
            retained = OUTPUT / suffix / ident
            retained.mkdir(parents=True, exist_ok=True)
            copies = {}
            names = {"compatibility.json": "compatibility.json",
                     "compatibility-analysis.log": "analysis.log",
                     "negative-analysis.log": "negative.log"}
            for name, kept_name in names.items():
                target = retained / kept_name
                old_target = retained / name
                if old_target != target and old_target.exists():
                    require(not target.exists() and old_target.read_bytes() ==
                            (original / name).read_bytes(),
                            "Retained diagnostic log changed before rename")
                    old_target.rename(target)
                content = (original / name).read_bytes()
                if target.exists():
                    require(target.read_bytes() == content, "Retained receipt changed: " + str(target))
                else:
                    target.write_bytes(content)
                copies[name] = {"path": str(target.relative_to(HERE)), "sha256": sha(target)}
            rows.append({"case_id": case, "candidate_id": ident,
                         "construction_sha256": candidate["construction_sha256"],
                         "files": copies, "diagnostic_only": True})
    require(len(rows) == 24, "Selected receipt export omitted a candidate")
    index = {"format": "c110454-selected-compatibility-retention-v1",
             "manifest_sha256": sha(MANIFEST), "candidate_count": len(rows),
             "candidates": rows, "physical_acceptance_claimed": False}
    path = HERE / "update025-source-receipts-index.json"
    path.write_text(json.dumps(index, indent=2) + "\n")
    return {"candidate_count": len(rows), "index_sha256": sha(path)}


if __name__ == "__main__":
    print(json.dumps(export()))
