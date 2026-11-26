"""Run six current-runtime diagnostic compatibility commands and retain receipts."""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

from build_construction import ROOT


REPO = ROOT.parents[1]
PRIVATE = REPO / ".runtime-work" / "c227824-compat-v5"
VALIDATOR = REPO / ".runtime-work" / "c229439-validator" / ".lake" / "build" / "bin" / "adapterCheck"


def main():
    if not VALIDATOR.is_file():
        raise ValueError("Pinned Lean validator missing")
    PRIVATE.mkdir(parents=True, exist_ok=True)
    cases = json.loads((ROOT / "case-plan.json").read_text())["cases"]
    rows = []
    receipts = {}
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["TMPDIR"] = str(PRIVATE)
    for case in cases:
        case_id = case["case_id"]
        suffix = case_id[len(ROOT.name) + 2:]
        output = PRIVATE / suffix
        if output.exists():
            shutil.rmtree(output)
        args = [sys.executable, str(REPO / "runtime.py"), "compatibility",
                "--manifest", str(ROOT / "execution-manifest.draft.json"),
                "--case", case_id, "--output", str(output),
                "--library", str(REPO / "runtime" / "library"),
                "--validator", str(VALIDATOR)]
        run = subprocess.run(args, cwd=REPO, env=env, capture_output=True,
                             text=True, timeout=600)
        if run.returncode:
            raise RuntimeError(case_id + ": " + run.stdout[-2000:] + run.stderr[-3000:])
        receipt = json.loads((output / "compatibility.json").read_text())
        if receipt.get("passed") is not True or receipt.get("case_id") != case_id:
            raise ValueError("compatibility receipt lost exact case or pass")
        target = ROOT / "cases" / suffix
        shutil.copyfile(output / "compatibility.json", target / "compatibility.json")
        shutil.copyfile(output / "compatibility-analysis.log", target / "cpu-compatibility-analysis.log")
        shutil.copyfile(output / "negative-analysis.log", target / "negative-analysis.log")
        receipts[case_id] = {
            "compatibility": {"receipt": f"cases/{suffix}/compatibility.json",
                              "sha256": hashlib.sha256((target / "compatibility.json").read_bytes()).hexdigest(),
                              "log": f"cases/{suffix}/cpu-compatibility-analysis.log"},
            "negative": {"log": f"cases/{suffix}/negative-analysis.log"},
            "acquisition": {
                name: {"entrypoint": "native_packets.py",
                       "method": "per-frame original Native packet join",
                       "evidence": path}
                for name, path in (("walker_body_history", "walker-body-history.jsonl"),
                                   ("facing_signal_history", "signal-history.jsonl"),
                                   ("other_device_history", "device-history.jsonl"),
                                   ("camera_frame_map", "video_frames.jsonl"))}}
        if case.get("sweep_id"):
            receipts[case_id]["acquisition"]["original_pedestrian_speed_mps"] = {
                "entrypoint": "analysis.py",
                "method": "source-joined original walker body-center displacement and time",
                "evidence": "walker-body-history.jsonl"}
        rows.append({"case_id": case_id, "compatibility_passed": True,
                     "checks": receipt["checks"],
                     "diagnostic_fixture_only": True})
    manifest_path = ROOT / "execution-manifest.draft.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        entry.update(receipts[entry["case_id"]])
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"format": "c227824-synthetic-compatibility-summary",
                      "cases": rows, "physical_acceptance_claimed": False}, indent=2))


if __name__ == "__main__":
    main()
