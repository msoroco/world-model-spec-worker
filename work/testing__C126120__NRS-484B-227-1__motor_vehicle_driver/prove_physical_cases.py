"""Exercise pinned physical completion on three synthetic outcomes per exact case."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
output_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
if not output_root.is_relative_to(REPO / ".runtime-work"):
    raise RuntimeError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path, rows):
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def fixture(folder, config, kind):
    folder.mkdir(parents=True, exist_ok=True)
    write(folder / "config.json", config)
    write(folder / "median-context.json", {"diagnostic_fixture": True, "case_id": config["selected_case_id"]})
    d = config["physical_completion"]
    if d["criterion"] == "turn":
        points = [(0, 0), (1, 0), (2, 1), (1, 2), (0, 2)]
        headings = [0, 45, 90, 135, 180]
    else:
        direction = d["direction_xy"]
        points = [(i * 2 * direction[0], i * 2 * direction[1]) for i in range(5)]
        headings = [0] * 5
    if kind == "incomplete_motion":
        points = [(0, 0)] * 5
        headings = [0] * 5
    body = []
    for i, ((x, y), heading) in enumerate(zip(points, headings)):
        body.append({"frame": i, "time_s": i / 20, "actor_id": 7,
                     "body_vertices_xy_m": [[x-.2,y-.2],[x+.2,y-.2],[x+.2,y+.2],[x-.2,y+.2]],
                     "heading_deg": heading})
    lines(folder / "trace.jsonl", [{"frame": row["frame"], "time_s": row["time_s"]} for row in body])
    lines(folder / "video_frames.jsonl", [{"carla_frame": row["frame"], "video_frame": row["frame"], "time_s": row["time_s"]} for row in body])
    if kind != "missing_evidence":
        lines(folder / "ego-body-history.jsonl", body)
    write(folder / "acquisition-provenance.json", {"diagnostic_fixture": True})
    result = physical_result(folder, {"case_id": config["selected_case_id"], "target_checks": []})
    expected = {"complete_motion": "met", "incomplete_motion": "not_met", "missing_evidence": "unverified"}[kind]
    assert result["physical_checks"]["maneuver"]["status"] == expected, (kind, result["physical_checks"]["maneuver"])
    assert result["maneuver_completed"] == (expected == "met")
    assert result["provenance_kind"] == "synthetic_fixture" and result["diagnostic_fixture"] is True
    return result


def lifecycle(folder, construction):
    folder.mkdir(parents=True, exist_ok=True)
    write(folder / "construction.json", construction)
    (folder / "runner.py").write_text("# diagnostic lifecycle source\n")
    lines(folder / "trace.jsonl", [{"frame": 0}])
    lines(folder / "video_frames.jsonl", [{"carla_frame": 0, "video_frame": 0, "time_s": 0}])
    write(folder / "acquisition-provenance.json", {"diagnostic_fixture": True})
    try:
        record_native_exit(folder)
    except Exception:
        pass
    else:
        raise AssertionError("Native exit accepted before closure")
    seal = seal_capture(folder, frames=1, restoration={"restored": True}, errors=[], encoder_exit_codes={"overview": 0})
    assert seal["events"] == ["capture_finished", "encoders_closed", "restoration_verified"]
    record_native_exit(folder)
    receipt = folder / "owner-release.json"
    try:
        acknowledge_owner_release(folder, receipt, False)
    except ValueError:
        pass
    else:
        raise AssertionError("Unacknowledged owner release accepted")
    # This fixture owns no CARLA resources; its synthetic owner is already released.
    acknowledge_owner_release(folder, receipt, True)
    return seal["events"] + ["native_exit", "owner_released", "saved_processing_started"]


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        case_folder = HERE / "cases" / suffix
        construction = json.loads((HERE / entry["construction"]).read_text())
        config_file = next(item for item in construction["files"] if item["path"] == "config.json")
        config = json.loads(config_file["content"])
        with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c126120-physical-") as tmp:
            temp = Path(tmp)
            fixtures = []
            for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
                result = fixture(temp / kind, config, kind)
                result_path = case_folder / f"physical-{kind}.json"
                log_path = case_folder / f"physical-{kind}.log"
                write(result_path, result)
                log_path.write_text(f"PINNED physical_result: {entry['case_id']} {kind} = {result['physical_checks']['maneuver']['status']}; synthetic diagnostic fixture; no CARLA acceptance\n")
                fixtures.append({"kind": kind, "command": "export SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c126120-direct-runtime; .venv-cpu/bin/python work/" + HERE.name + "/prove_physical_cases.py",
                                 "exit_code": 0, "log": str(log_path.relative_to(HERE)), "log_sha256": sha(log_path),
                                 "result": str(result_path.relative_to(HERE)), "result_sha256": sha(result_path)})
            events = lifecycle(temp / "lifecycle", construction)
        life_log = case_folder / "physical-lifecycle.log"
        life_log.write_text("Pinned seal_capture, record_native_exit, acknowledge_owner_release ordering; no CARLA resources in synthetic fixture.\n" + " -> ".join(events) + "\n")
        receipt = {"construction_sha256": entry["construction_sha256"], "fixtures": fixtures,
                   "lifecycle": {"events": events, "exit_code": 0, "log": str(life_log.relative_to(HERE)), "log_sha256": sha(life_log)}}
        receipt_path = case_folder / "physical-preparation.json"
        write(receipt_path, receipt)
        entry["physical_preparation"] = {"receipt": str(receipt_path.relative_to(HERE)), "sha256": sha(receipt_path)}
        print(suffix, "three pinned physical outcomes and ordered lifecycle passed")
    write(manifest_path, manifest)


if __name__ == "__main__":
    main()
