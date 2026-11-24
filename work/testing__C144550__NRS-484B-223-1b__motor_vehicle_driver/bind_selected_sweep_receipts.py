"""Bind selected source-bound compatibility receipts without changing their bytes."""

import hashlib
import json
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    bound = []
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        if "pending-" not in suffix:
            continue
        replayed = suffix.startswith("signal-")
        source = ROOT / ".runtime-work" / f"c144550-selected-compat-{'current-' if replayed else ''}{suffix}"
        if not (source / "compatibility.json").is_file():
            continue
        destination = HERE / "sweep-cases" / suffix
        paths = {
            "compatibility.json": "selected-compatibility.json",
            "compatibility-analysis.log": "selected-analysis.log",
            "negative-analysis.log": "selected-negative.log",
        }
        for name, target in paths.items():
            shutil.copyfile(source / name, destination / target)
        receipt = json.loads((destination / "selected-compatibility.json").read_text())
        assert receipt["case_id"] == entry["case_id"]
        assert receipt["construction_sha256"] == entry["construction_sha256"]
        assert receipt["runtime_manifest_sha256"] == manifest["runtime_manifest_sha256"]
        prefix = f"sweep-cases/{suffix}/"
        entry["compatibility"] = {
            "receipt": prefix + "selected-compatibility.json",
            "sha256": sha(destination / "selected-compatibility.json"),
            "log": prefix + "selected-analysis.log",
        }
        entry["negative"] = {"log": prefix + "selected-negative.log"}
        saved = ROOT / ".runtime-work" / f"c144550-selected-saved-{'current-' if replayed else ''}{suffix}" / "v0001/processing.json"
        if saved.is_file():
            shutil.copyfile(saved, destination / "selected-processing.json")
            saved_log = destination / ("selected-saved-current.log" if replayed else "selected-saved.log")
            entry["post_capture"] = {
                "recorded_only": True,
                "command": "SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c144550-selected-replay .venv-cpu/bin/python runtime.py process-saved --manifest work/" + HERE.name + "/execution-manifest.json --case " + entry["case_id"] + " --attempt .runtime-work/c144550-selected-compat-" + ("current-" if replayed else "") + suffix + " --output .runtime-work/c144550-selected-saved-" + ("current-" if replayed else "") + suffix,
                "test_log": prefix + saved_log.name,
                "test_log_sha256": sha(saved_log),
                "test_exit_code": 0,
                "processing_receipt": prefix + "selected-processing.json",
                "processing_sha256": sha(destination / "selected-processing.json"),
            }
        for channel in json.loads((HERE / entry["construction"]).read_text())["recording_description"]["channels"]:
            if channel["name"] in ("appropriate_signal_lead_frames", "nearest_target_body_gap_at_departure_m"):
                entry["acquisition"][channel["name"]] = {
                    "entrypoint": "lane_change_measurements.py",
                    "method": channel["method"],
                    "evidence": "original lane_history.jsonl, lane_context.json, video_frames.jsonl and trace.jsonl; channels/" + channel["name"] + ".jsonl",
                }
        bound.append(suffix)
    zero = next(e for e in manifest["cases"] if e["case_id"].endswith("__left_signal_at_departure_clear_gap"))
    folder = HERE / "cases/left_signal_at_departure_clear_gap"
    receipt = json.loads((folder / "primary-compatibility.json").read_text())
    assert receipt["construction_sha256"] == zero["construction_sha256"]
    assert receipt["runtime_manifest_sha256"] == manifest["runtime_manifest_sha256"]
    zero["compatibility"] = {
        "receipt": "cases/left_signal_at_departure_clear_gap/primary-compatibility.json",
        "sha256": sha(folder / "primary-compatibility.json"),
        "log": "cases/left_signal_at_departure_clear_gap/primary-compatibility-analysis.log",
    }
    zero["negative"] = {"log": "cases/left_signal_at_departure_clear_gap/primary-negative-analysis.log"}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"bound_sweeps": bound, "bound_zero": True}))


if __name__ == "__main__":
    main()
