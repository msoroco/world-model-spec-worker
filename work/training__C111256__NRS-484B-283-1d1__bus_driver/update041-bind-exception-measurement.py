"""Bind the selected exception-context output to all exact Walk bundles.

This invalidates old construction-bound receipts. It never claims that a CPU
fixture established original exception applicability.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def main():
    path = HERE / "execution-manifest.json"
    prior = HERE / "update041-prior-execution-manifest.json"
    if prior.exists():
        raise ValueError("Prior manifest already retained; do not overwrite")
    prior.write_bytes(path.read_bytes())
    manifest = json.loads(path.read_text())
    finalizer = (HERE / "native/finalize.py").read_text()
    row = {
        "disposition_index": 0,
        "requirement": "text-0",
        "source": "inputs/coverage/branch-sources.json",
        "output_key": "exception_context_observation",
        "method": "measure_exception_context",
        "value_type": "object",
        "kind": "sourced_context",
        "inputs": ["native_samples.jsonl", "video_frames.jsonl", "road_geometry.json"],
    }
    bundles = 0
    for case in manifest["cases"]:
        contract_path = HERE / case["measurement_contract"]
        contract = json.loads(contract_path.read_text())
        if any(item["disposition_index"] == 0 for item in contract["requirements"]):
            raise ValueError("Exception requirement already bound: " + case["case_id"])
        contract["requirements"].insert(0, row.copy())
        contract["original_source_gates"].append(
            "independent original NRS 484B.287, 484B.290 and 484B.350 applicability review"
        )
        write(contract_path, contract)
        for candidate in (case, *case["candidates"]):
            construction_path = HERE / candidate["construction"]
            construction = json.loads(construction_path.read_text())
            files = {item["path"]: item for item in construction["files"]}
            files["finalize.py"]["content"] = finalizer
            write(construction_path, construction)
            candidate["construction_sha256"] = sha(construction_path)
            candidate.pop("offline", None)
            candidate.pop("compatibility", None)
            bundles += 1
        for key in ("negative", "physical_preparation", "delivery_acceptance", "post_capture"):
            case.pop(key, None)
        case["preparation_status"] = "selected; exception measurement rebound; CPU reproof pending"
    manifest["selection_review"]["law_input_sha256"] = sha(ROOT / "inputs" / HERE.name / "assignment.json")
    manifest["selection_review"]["case_plan_sha256"] = sha(HERE / "case-plan.json")
    manifest["selection_review"]["draft_proposal_sha256"] = sha(HERE / "proposals/cases.json")
    manifest["selection_review"]["scope"] = (
        "Six exact CPU delivery cases; all selected requirement outputs now bound. "
        "Original Walk and exception applicability remain pending independent source review."
    )
    manifest.pop("selected_sweep_delivery_matrix_sha256", None)
    manifest["status"] = "selected_cpu_reproof_pending"
    write(path, manifest)
    print(json.dumps({"selected_cases": len(manifest["cases"]), "bundles_rebound": bundles,
                      "manifest_sha256": sha(path), "prior_manifest_sha256": sha(prior),
                      "original_exception_applicability_verified": False}))


if __name__ == "__main__":
    main()
