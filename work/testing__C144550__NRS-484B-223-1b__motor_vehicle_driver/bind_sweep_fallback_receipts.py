"""Bind tested sweep fallback offline, compatibility and saved receipts."""

import hashlib
import json
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    bound = []
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        if "pending-" not in suffix:
            continue
        candidate = entry["candidates"][0]
        assert candidate["id"] == "fallback1"
        folder = HERE / "sweep-cases" / suffix
        source = ROOT / ".runtime-work" / f"c144550-sweep-fallback-compat-{suffix}"
        saved = ROOT / ".runtime-work" / f"c144550-sweep-fallback-saved-{suffix}" / "v0001/processing.json"
        for old, new in (
            (source / "compatibility.json", "fallback1-compatibility.json"),
            (source / "compatibility-analysis.log", "fallback1-analysis.log"),
            (source / "negative-analysis.log", "fallback1-negative.log"),
            (saved, "fallback1-processing.json"),
        ):
            shutil.copyfile(old, folder / new)
        receipt = json.loads((folder / "fallback1-compatibility.json").read_text())
        processing = json.loads((folder / "fallback1-processing.json").read_text())
        assert receipt["case_id"] == processing["case_id"] == entry["case_id"]
        assert receipt["candidate_id"] == processing["candidate_id"] == "fallback1"
        assert receipt["construction_sha256"] == candidate["construction_sha256"]
        assert receipt["runtime_manifest_sha256"] == manifest["runtime_manifest_sha256"]
        assert processing["passed"] and processing["recorded_only"] and processing["originals_preserved"]
        prefix = f"sweep-cases/{suffix}/"
        offline = folder / "fallback1-offline.log"
        assert '"offline_passed": true' in offline.read_text()
        candidate["offline"] = {
            "command": "SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c144550-sweep-fallback-offline .venv-cpu/bin/python runtime.py offline --manifest work/" + HERE.name + "/execution-manifest.json --case " + entry["case_id"] + " --candidate fallback1 --output .runtime-work/c144550-sweep-fallback-offline-" + suffix,
            "exit_code": 0,
            "construction_sha256": candidate["construction_sha256"],
            "log": prefix + "fallback1-offline.log",
            "log_sha256": sha(offline),
        }
        candidate["compatibility"] = {
            "receipt": prefix + "fallback1-compatibility.json",
            "sha256": sha(folder / "fallback1-compatibility.json"),
            "log": prefix + "fallback1-analysis.log",
            "negative_log": prefix + "fallback1-negative.log",
        }
        candidate["post_capture"] = {
            "recorded_only": True,
            "command": "SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c144550-sweep-fallback-proof .venv-cpu/bin/python runtime.py process-saved --manifest work/" + HERE.name + "/execution-manifest.json --case " + entry["case_id"] + " --attempt .runtime-work/c144550-sweep-fallback-compat-" + suffix + " --output .runtime-work/c144550-sweep-fallback-saved-" + suffix,
            "test_log": prefix + "fallback1-saved.log",
            "test_log_sha256": sha(folder / "fallback1-saved.log"),
            "test_exit_code": 0,
            "processing_receipt": prefix + "fallback1-processing.json",
            "processing_sha256": sha(folder / "fallback1-processing.json"),
        }
        candidate["status"] = "cpu_offline_compatibility_saved_passed"
        bound.append(entry["case_id"])
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"bound_sweep_fallbacks": bound}))


if __name__ == "__main__":
    main()
