"""Independent CPU audit of twenty source-bound candidate delivery preparations."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit(root=HERE, manifest=None, result=None):
    root = Path(root)
    manifest = manifest or json.loads((root / "execution-manifest.json").read_text())
    result = result or json.loads((root / "result.json").read_text())
    require(len(manifest.get("cases", [])) == 5 and
            result.get("assignment_id") == manifest.get("assignment_id") and
            result.get("status") in ("partial", "ready"),
            "Five matching selected cases and truthful result required")
    rows = []
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        candidates = entry.get("candidates", [])
        require(len(candidates) == 3 and
                {c.get("id") for c in candidates} == {"fallback1", "fallback2", "fallback3"},
                "Three exact fallback constructions required: " + case_id)
        require(entry.get("candidate_risk", {}).get("status") == "physical" and
                len({tuple(c.get("changed_knobs", [])) for c in candidates}) == 3 and
                all(c.get("trigger", {}).get("source") and
                    c["trigger"].get("metric") and
                    c["trigger"].get("failure_condition") for c in candidates),
                "Distinct measurable physical risks required: " + case_id)
        for candidate_id, selected in [("primary", entry)] + [(c["id"], c) for c in candidates]:
            label = case_id + "/" + candidate_id
            construction = root / selected["construction"]
            digest = selected["construction_sha256"]
            require(construction.is_file() and sha(construction) == digest,
                    "Changed exact construction: " + label)
            bundle = json.loads(construction.read_text())
            require(bundle.get("case_id") == case_id and bundle.get("actor") == "motor_vehicle_driver",
                    "Wrong selected construction identity: " + label)
            offline = selected.get("offline", {})
            log = root / offline.get("log", "__missing__")
            require(offline.get("exit_code") == 0 and
                    offline.get("construction_sha256") == digest and
                    log.is_file() and sha(log) == offline.get("log_sha256") and
                    any(test.get("command") == offline.get("command") and
                        test.get("exit_code") == 0 and
                        test.get("log") == offline.get("log") and
                        test.get("sha256") == offline.get("log_sha256")
                        for test in result.get("tests", [])),
                    "Missing exact offline CPU proof: " + label)
            compatible = selected.get("compatibility_diagnostic", {})
            receipt_path = root / compatible.get("receipt", "__missing__")
            require(compatible.get("exit_code") == 0 and receipt_path.is_file() and
                    sha(receipt_path) == compatible.get("sha256"),
                    "Missing bound compatibility proof: " + label)
            receipt = json.loads(receipt_path.read_text())
            require(receipt.get("passed") is True and receipt.get("case_id") == case_id and
                    receipt.get("candidate_id") == candidate_id and
                    receipt.get("construction_sha256") == digest and
                    receipt.get("negative_removed") == "crossing_history.jsonl" and
                    "Missing required source" in receipt.get("negative_error_contains", "") and
                    receipt.get("negative_log_sha256") and
                    {"actual_analysis", "negative_case_source", "four_camera_sources",
                     "native_validation", "lean_decoder", "final_decode"}
                    <= set(receipt.get("checks", [])),
                    "Incomplete positive/negative compatibility: " + label)
            saved_info = selected.get("saved_processing_diagnostic", {})
            saved_path = root / saved_info.get("receipt", "__missing__")
            require(saved_info.get("exit_code") == 0 and saved_info.get("recorded_only") is True and
                    saved_path.is_file() and sha(saved_path) == saved_info.get("sha256"),
                    "Missing bound recorded-only proof: " + label)
            saved = json.loads(saved_path.read_text())
            require(saved.get("passed") is True and saved.get("case_id") == case_id and
                    saved.get("candidate_id") == candidate_id and
                    saved.get("recorded_only") is True and
                    saved.get("originals_preserved") is True and
                    saved.get("physical_acceptance_claimed") is False and
                    saved.get("legal_acceptance_claimed") is False and
                    saved.get("native_revision", {}).get("construction_sha256") == digest,
                    "Saved-only original-source processing incomplete: " + label)
            rows.append({"case_id": case_id, "candidate_id": candidate_id,
                         "construction_sha256": digest,
                         "compatibility_sha256": compatible["sha256"],
                         "saved_sha256": saved_info["sha256"]})
    return {"format": "worker-c125697-sub1-delivery-audit", "passed": True,
            "exact_constructions": len(rows), "proofs": rows,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
