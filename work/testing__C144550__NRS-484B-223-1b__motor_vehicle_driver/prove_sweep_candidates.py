"""Verify returned CPU sweep constructions and source-derived receipts."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove():
    manifest_path = HERE / "sweep-execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest["runtime_manifest_sha256"] != sha(ROOT / "runtime/SOURCE-MANIFEST.json"):
        raise ValueError("Sweep manifest binds another runtime")
    if len(manifest["cases"]) != 5:
        raise ValueError("Five generated sweep cases required")
    expected = {
        "signal-appropriateness-pending-0000": ("appropriate_signal_lead_frames", -1.0, "frames"),
        "signal-appropriateness-pending-0001": ("appropriate_signal_lead_frames", 1.0, "frames"),
        "signal-appropriateness-pending-0002": ("appropriate_signal_lead_frames", 0.0, "frames"),
        "safety-ascertainment-pending-0000": ("nearest_target_body_gap_at_departure_m", 3.0, "m"),
        "safety-ascertainment-pending-0001": ("nearest_target_body_gap_at_departure_m", 8.0, "m"),
    }
    rows = []
    for entry in manifest["cases"]:
        case = entry["case_id"]
        if case not in expected:
            raise ValueError("Unknown sweep case")
        folder = HERE / "sweep-cases" / case
        name, value, unit = expected[case]
        construction = HERE / entry["construction"]
        if sha(construction) != entry["construction_sha256"]:
            raise ValueError("Construction hash changed: " + case)
        offline_text = (folder / "offline.log").read_text()
        if '"offline_passed": true' not in offline_text or '"case_id": "' + case + '"' not in offline_text:
            raise ValueError("Offline CPU proof missing: " + case)
        compatibility = json.loads((folder / "compatibility.json").read_text())
        if not (compatibility["passed"] is True and compatibility["case_id"] == case and
                compatibility["candidate_id"] == "primary" and
                compatibility["construction_sha256"] == entry["construction_sha256"] and
                compatibility["runtime_manifest_sha256"] == manifest["runtime_manifest_sha256"] and
                compatibility["negative_log_sha256"] == sha(folder / "negative-analysis.log") and
                compatibility["log_sha256"] == sha(folder / "source-analysis.log")):
            raise ValueError("Compatibility proof changed: " + case)
        if not {"actual_analysis", "negative_case_source", "lean_decoder", "final_decode"} <= set(compatibility["checks"]):
            raise ValueError("Compatibility checks incomplete: " + case)
        result = json.loads((folder / "source-result.json").read_text())
        measured = result["realized_observables"].get(name)
        if not measured or measured["unit"] != unit or measured["value"] != value:
            raise ValueError("Source-derived sweep observation changed: " + case)
        stream = [json.loads(line) for line in (folder / (name + ".jsonl")).read_text().splitlines()]
        if len(stream) != 1 or stream[0]["value"] != value or measured["sample_window_s"] != [stream[0]["time_s"]] * 2:
            raise ValueError("Sweep event stream differs from summary: " + case)
        saved = json.loads((folder / "saved-processing.json").read_text())
        if not (saved["passed"] is True and saved["recorded_only"] is True and
                saved["case_id"] == case and saved["candidate_id"] == "primary" and
                saved["originals_preserved"] is True and
                saved["analysis_log_sha256"] == sha(folder / "saved-analysis.log")):
            raise ValueError("Saved processing proof changed: " + case)
        rows.append({"case_id": case, "source_observable": name, "measured_value": value,
                     "unit": unit, "construction_sha256": entry["construction_sha256"],
                     "offline_log_sha256": sha(folder / "offline.log"),
                     "compatibility_receipt_sha256": sha(folder / "compatibility.json"),
                     "compatibility_result_sha256": sha(folder / "source-result.json"),
                     "saved_receipt_sha256": sha(folder / "saved-processing.json")})
    return {"format": "worker-c144550-sweep-candidate-replay",
            "manifest_sha256": sha(manifest_path), "runtime_manifest_sha256": manifest["runtime_manifest_sha256"],
            "cases": rows, "selected_for_delivery": False, "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False}


if __name__ == "__main__":
    report = prove()
    (HERE / "sweep-candidate-replay.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"verified_case_ids": [row["case_id"] for row in report["cases"]]}, sort_keys=True))
