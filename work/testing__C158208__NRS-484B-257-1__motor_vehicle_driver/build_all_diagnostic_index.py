"""Seal all eleven diagnostic CPU proof logs without claiming original delivery."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work" / "c158208-nov25b"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    manifest_path = HERE / "execution-manifest.diagnostic.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("status") != "diagnostic_compatibility_only_original_source_pending":
        raise ValueError("diagnostic manifest status differs")
    accepted = json.loads((HERE / "statutory-matrix.draft.json").read_text())["accepted_recordings"]
    if {entry["case_id"] for entry in manifest["cases"]} != set(accepted):
        raise ValueError("diagnostic proof inventory differs from frozen accepted cases")
    proofs = []
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        kind = case_id.rsplit("__", 1)[-1]
        logs = {}
        for phase in ("offline", "compatibility", "saved"):
            path = HERE / f"cpu-all-{kind}-{phase}.log"
            data = json.loads(path.read_text())
            if data.get("case_id") != case_id:
                raise ValueError("diagnostic phase case identity differs: " + kind)
            success = (data.get("offline_passed") if phase == "offline"
                       else data.get("passed"))
            if success is not True:
                raise ValueError("diagnostic phase did not pass: " + kind + " " + phase)
            logs[phase] = {"path": path.name, "sha256": sha(path)}
        receipt_path = SCRATCH / ("all-compat-" + kind) / "compatibility.json"
        receipt = json.loads(receipt_path.read_text())
        if (receipt.get("case_id") != case_id or receipt.get("passed") is not True or
                receipt.get("construction_sha256") != entry["construction_sha256"] or
                receipt.get("scope") != "diagnostic software compatibility only"):
            raise ValueError("diagnostic compatibility receipt differs: " + kind)
        proofs.append({"case_id": case_id, "construction_sha256": entry["construction_sha256"],
                       "fixture_recipe_sha256": sha(HERE / f"fixture-recipe-{kind}.json"),
                       "measurement_contract_sha256": sha(HERE / f"measurement-contract-{kind}.json"),
                       "logs": logs, "compatibility_receipt_sha256": sha(receipt_path),
                       "compatibility_receipt": receipt,
                       "physical_acceptance_claimed": False})
    comparison = HERE / "diagnostic-comparison-all.json"
    checked = json.loads(comparison.read_text())
    if checked.get("diagnostic_fixture") is not True or len(checked.get("comparisons", [])) != 8:
        raise ValueError("eight diagnostic comparisons required")
    result = {"format": "c158208-all-diagnostic-cpu-index-v1",
              "assignment_id": HERE.name,
              "manifest_sha256": sha(manifest_path),
              "diagnostic_only": True, "source_kind": "synthetic_fixture",
              "case_proofs": proofs,
              "comparison_sha256": sha(comparison),
              "selection_status": "original_sources_and_source_grounded_sweeps_pending",
              "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}
    target = HERE / "diagnostic-compatibility-index-all.json"
    encoded = (json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode()
    if len(encoded) > 2 * 1024 * 1024:
        raise ValueError("diagnostic proof index exceeds returned-file limit")
    target.write_bytes(encoded)
    return {"cases": len(proofs), "comparisons": len(checked["comparisons"]),
            "index_sha256": sha(target)}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
