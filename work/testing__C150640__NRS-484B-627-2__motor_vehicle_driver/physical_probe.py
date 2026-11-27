"""Exercise three source-shaped motion outcomes and ordered saved lifecycle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def fixture(folder, config, construction, kind):
    folder.mkdir()
    write(folder / "config.json", config)
    write(folder / "construction.json", construction)
    (folder / "runner.py").write_text(next(item["content"] for item in construction["files"]
                                           if item["path"] == "runner.py"), encoding="utf-8")
    write(folder / "acquisition-provenance.json", {
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True})
    if kind == "missing_evidence":
        return
    positions = [float(i) for i in range(9)] if kind == "complete_motion" else [i / 20 for i in range(9)]
    trace, mapping = [], []
    for index, x in enumerate(positions):
        frame, time_s = 200 + index, index / 20
        trace.append({"frame": frame, "time_s": time_s, "position_m": [x, 0, 0],
                      "position": {"x": x, "y": 0, "z": 0},
                      "heading_deg": 0, "speed_mps": 1})
        mapping.append({"video_frame": index, "carla_frame": frame, "time_s": time_s})
    for name, rows in (("trace.jsonl", trace), ("video_frames.jsonl", mapping)):
        (folder / name).write_text("".join(json.dumps(row) + "\n" for row in rows),
                                   encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    from worker_exchange.native_output import physical_result, seal_capture
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, copy_sources
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    entry = next(item for item in manifest["cases"] if item["case_id"] == args.case)
    construction = json.loads((ROOT / entry["construction"]).read_text())
    config = json.loads(next(item["content"] for item in construction["files"]
                             if item["path"] == "config.json"))
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    for kind, expected in (("complete_motion", "met"), ("incomplete_motion", "not_met"),
                           ("missing_evidence", "unverified")):
        folder = output / kind
        fixture(folder, config, construction, kind)
        target = {"target": "observed two-vehicle approach and stop or slow-roll episode",
                  "requested": True, "measured": kind == "complete_motion",
                  "method": "synthetic original-shaped path", "tolerance": 0,
                  "matched": kind == "complete_motion", "physical_cause_confirmed": False,
                  "cause_evidence": "diagnostic trace"}
        result = physical_result(folder, {"target_checks": [target]})
        if result["physical_checks"]["maneuver"]["status"] != expected:
            raise ValueError("physical outcome mismatch: " + kind)
        write(ROOT / ("physical-" + args.case.split("__")[-1] + "-" + kind + ".json"), result)
        print(kind, expected, sorted(result["physical_checks"]["maneuver"]["sources"]))
    complete = output / "complete_motion"
    seal = seal_capture(complete, frames=9,
                        restoration={"restored": True,
                                     "settings_readback": "synthetic protocol fixture"},
                        errors=[], encoder_exit_codes={"synthetic": 0})
    native_exit = record_native_exit(complete)
    owner = acknowledge_owner_release(complete, complete / "owner-release.json", True)
    stage = output / "saved_stage"
    stage.mkdir()
    copy_sources(complete, stage)
    if (not native_exit["capture_seal_sha256"] or not owner["native_exit_sha256"]
            or not (stage / "trace.jsonl").is_file()):
        raise ValueError("closure or saved source staging failed")
    print("lifecycle", *seal["events"], "native_exit", "owner_released",
          "saved_processing_started")


if __name__ == "__main__":
    main()
