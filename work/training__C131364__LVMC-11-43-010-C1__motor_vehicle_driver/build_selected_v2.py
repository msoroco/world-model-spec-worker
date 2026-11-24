"""Bind the paired CPU-proved constructions to an exact selected draft."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def receipt(path):
    return {"path": path, "sha256": digest(path)}


def main():
    draft = json.loads((ROOT / "v2-fallback-draft-manifest.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    selected = []
    for index, entry in enumerate(draft["cases"], 1):
        witness = f"witness_{index}"
        primary = f"selected-v2/proofs/witness{index}-primary"
        fallback = f"selected-v2/proofs/witness{index}-fallback1"
        case = dict(entry)
        case["kind"] = "delivery"
        case["preparation_status"] = "selected_cpu_proofs_physical_unverified"
        case["primary_proofs"] = {
            "offline": receipt(f"{primary}/offline.log"),
            "compatibility": receipt(f"{primary}/compatibility.json"),
            "missing_source_negative": receipt(f"{primary}/negative-analysis.log"),
            "recorded_only_processing": receipt(f"{primary}/processing.json"),
        }
        candidate = dict(case["candidates"][0])
        candidate["proofs"] = {
            "offline": receipt(f"{fallback}/offline.log"),
            "compatibility": receipt(f"{fallback}/compatibility.json"),
            "missing_source_negative": receipt(f"{fallback}/negative-analysis.log"),
            "recorded_only_processing": receipt(f"{fallback}/processing.json"),
        }
        case["candidates"] = [candidate]
        case["post_capture"] = {
            "recorded_only": True,
            "command": f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{ASSIGNMENT}/selected-v2-manifest.json --case {case["case_id"]} --attempt "$ATTEMPT" --output "$OUTPUT" --library "$LIBRARY" --validator "$VALIDATOR"',
            "diagnostic_receipt": case["primary_proofs"]["recorded_only_processing"],
        }
        selected.append(case)
    output = {
        "format": "worker-execution-manifest",
        "assignment_id": ASSIGNMENT,
        "runtime_manifest_sha256": draft["runtime_manifest_sha256"],
        "status": "selected_cpu_partial_physical_unverified",
        "selected_case_ids": [case["case_id"] for case in selected],
        "comparisons": [{
            **plan["comparisons"][0],
            "fixed_conditions": [
                "same frozen cell, law, actor, authored road and non-target actors",
                "same 30-second 20-Hz four-camera recording and source-packet contract",
                "same controller source, requested speed and capture/finalizer implementation",
                "same original frame/time grid; route position, heading and phase may respond to the requested circulating lane",
            ],
            "isolation_audit": "selected-v2/audit.json",
        }],
        "cases": selected,
        "independent_cpu_audits": [
            receipt("v2-native-draft/audit.json"),
            receipt("v2-fallback-draft/audit.json"),
            receipt("v2-native-draft/fake-native-test.log"),
        ],
        "physical_acceptance_claimed": False,
        "legal_verdict_claimed": False,
    }
    (ROOT / "selected-v2-manifest.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n"
    )
    print(digest("selected-v2-manifest.json"))


if __name__ == "__main__":
    main()
