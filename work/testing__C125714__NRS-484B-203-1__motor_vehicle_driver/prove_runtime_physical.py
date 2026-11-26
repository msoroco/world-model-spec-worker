"""Exercise each selected original-motion criterion through the pinned assessor."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.native_output import assess_physical


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def main():
    output_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "/nonexistent")).resolve()
    if REPO / ".runtime-work" not in output_root.parents:
        raise ValueError("Set output root under .runtime-work")
    scratch = REPO / ".runtime-work/c125714-repair-physical"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    results = []
    manifest = json.loads((ROOT / "manifest.draft.json").read_text())
    for entry in manifest["cases"]:
        short = entry["case_id"].split("__")[-1]
        config_path = ROOT / "config.json" if short == "right_half" else ROOT / "cases" / short / "config.json"
        cfg = json.loads(config_path.read_text())
        case_root = scratch / short
        case_root.mkdir()
        write(case_root / "config.json", cfg)
        mapping = [{"video_frame": i, "carla_frame": i + 1, "time_s": .05 * (i + 1)}
                   for i in range(3)]
        (case_root / "video_frames.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in mapping))
        statuses = {}
        for kind, positions, expected in (
                ("complete", (0., 2., 5.), "met"),
                ("incomplete", (0., .2, .4), "not_met")):
            rows = [{"frame": i + 1, "time_s": .05 * (i + 1),
                     "position_m": [x, 0., 0.]} for i, x in enumerate(positions)]
            (case_root / "trace.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows))
            status = assess_physical(case_root, cfg)["physical_checks"]["maneuver"]["status"]
            if status != expected:
                raise ValueError(f"{short} {kind}: {status} != {expected}")
            statuses[kind] = status
        (case_root / "trace.jsonl").unlink()
        status = assess_physical(case_root, cfg)["physical_checks"]["maneuver"]["status"]
        if status != "unverified":
            raise ValueError(f"{short} missing: {status} != unverified")
        statuses["missing"] = status
        results.append({"case_id": entry["case_id"],
                        "criterion": cfg["physical_completion"]["criterion"],
                        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
                        "status_by_fixture": statuses})
    receipt = {"format": "c125714-pinned-runtime-physical-proof",
               "cases": results, "diagnostic_fixture": True,
               "scope": "Synthetic assessor protocol; original CARLA opposing-pass motion and legal context pending"}
    write(ROOT / "cpu-runtime-physical-proof.json", receipt)
    print(json.dumps({"cases": len(results), "status": "passed"}, sort_keys=True))


if __name__ == "__main__":
    main()
