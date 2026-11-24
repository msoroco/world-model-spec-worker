"""Bind current-runtime original primary receipts after compatibility/saved replay."""

import hashlib
import json
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUFFIXES = (
    "left_signal_late_clear_gap",
    "left_wrong_signal_clear_gap",
    "left_signal_before_close_gap",
    "right_signal_before_clear_gap",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    bound = []
    for suffix in SUFFIXES:
        case_id = HERE.name + "__" + suffix
        entry = next(item for item in manifest["cases"] if item["case_id"] == case_id)
        source = ROOT / ".runtime-work" / f"c144550-original-four-compat-{suffix}"
        saved = ROOT / ".runtime-work" / f"c144550-original-four-saved-{suffix}" / "v0001/processing.json"
        destination = HERE / "cases" / suffix
        for src, target in (
            (source / "compatibility.json", "current-selected-compatibility.json"),
            (source / "compatibility-analysis.log", "current-selected-analysis.log"),
            (source / "negative-analysis.log", "current-selected-negative.log"),
            (saved, "current-selected-processing.json"),
        ):
            shutil.copyfile(src, destination / target)
        receipt = json.loads((destination / "current-selected-compatibility.json").read_text())
        processing = json.loads((destination / "current-selected-processing.json").read_text())
        assert receipt["case_id"] == processing["case_id"] == case_id
        assert receipt["construction_sha256"] == entry["construction_sha256"]
        assert receipt["runtime_manifest_sha256"] == manifest["runtime_manifest_sha256"]
        assert processing["passed"] and processing["recorded_only"] and processing["originals_preserved"]
        prefix = f"cases/{suffix}/"
        entry["compatibility"] = {
            "receipt": prefix + "current-selected-compatibility.json",
            "sha256": sha(destination / "current-selected-compatibility.json"),
            "log": prefix + "current-selected-analysis.log",
        }
        entry["negative"] = {"log": prefix + "current-selected-negative.log"}
        entry["post_capture"] = {
            "recorded_only": True,
            "command": "SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c144550-original-four-rebind .venv-cpu/bin/python runtime.py process-saved --manifest work/" + HERE.name + "/execution-manifest.json --case " + case_id + " --attempt .runtime-work/c144550-original-four-compat-" + suffix + " --output .runtime-work/c144550-original-four-saved-" + suffix,
            "test_log": prefix + "current-selected-saved.log",
            "test_log_sha256": sha(destination / "current-selected-saved.log"),
            "test_exit_code": 0,
            "processing_receipt": prefix + "current-selected-processing.json",
            "processing_sha256": sha(destination / "current-selected-processing.json"),
        }
        bound.append(case_id)
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"bound_original_primaries": bound}))


if __name__ == "__main__":
    main()
