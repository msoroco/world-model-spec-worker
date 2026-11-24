"""Exercise three pinned reversal outcomes and the saved-capture lifecycle."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work"
OUTPUT = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
TEMPORARY = Path(os.environ.get("TMPDIR", "")).resolve()
if not OUTPUT.is_relative_to(SCRATCH) or not TEMPORARY.is_relative_to(SCRATCH):
    raise RuntimeError("Export runtime output and temporary roots under .runtime-work")
sys.path.insert(0, str(REPO / "runtime" / "scenario_pipeline"))
from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def lines(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def physical_fixture(folder: Path, config: dict, kind: str) -> dict:
    folder.mkdir(parents=True)
    write(folder / "config.json", config)
    write(folder / "curve_context.json", {"diagnostic_fixture": True,
                                           "case_id": config["selected_case_id"],
                                           "location_kind": "curve"})
    points = [(0, 0), (1, 0), (2, 1), (1, 2), (0, 2)]
    headings = [0, 45, 90, 135, 180]
    if kind == "incomplete_motion":
        points = [(0, 0)] * 5
        headings = [0] * 5
    body = []
    for frame, ((x, y), heading) in enumerate(zip(points, headings)):
        body.append({"frame": frame, "time_s": frame / 20,
                     "body_vertices_m": [[x - .2, y - .2], [x + .2, y - .2],
                                         [x + .2, y + .2], [x - .2, y + .2]],
                     "heading_deg": heading,
                     "cumulative_heading_change_deg": heading})
    lines(folder / "trace.jsonl", [{"frame": row["frame"], "time_s": row["time_s"],
                                    "heading_deg": row["heading_deg"]} for row in body])
    lines(folder / "video_frames.jsonl", [
        {"carla_frame": row["frame"], "video_frame": row["frame"],
         "time_s": row["time_s"]} for row in body])
    if kind != "missing_evidence":
        lines(folder / "turn_history.jsonl", body)
    write(folder / "acquisition-provenance.json", {
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True})
    result = physical_result(folder, {"case_id": config["selected_case_id"],
                                      "target_checks": []})
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[kind]
    assert result["physical_checks"]["maneuver"]["status"] == expected
    assert result["maneuver_completed"] == (expected == "met")
    assert result["provenance_kind"] == "synthetic_fixture"
    assert result["diagnostic_fixture"] is True
    return result


def lifecycle(folder: Path, construction: dict) -> list[str]:
    folder.mkdir(parents=True)
    write(folder / "construction.json", construction)
    runner = next(file["content"] for file in construction["files"]
                  if file["path"] == "runner.py")
    (folder / "runner.py").write_text(runner)
    lines(folder / "trace.jsonl", [{"frame": 0, "time_s": 0}])
    lines(folder / "video_frames.jsonl", [
        {"carla_frame": 0, "video_frame": 0, "time_s": 0}])
    write(folder / "acquisition-provenance.json", {
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True})
    try:
        record_native_exit(folder)
    except (ValueError, FileNotFoundError):
        pass
    else:
        raise AssertionError("Unsealed Native exit accepted")
    seal = seal_capture(folder, frames=1, restoration={"restored": True},
                        errors=[], encoder_exit_codes={"overview": 0})
    record_native_exit(folder)
    owner = folder / "owner-release.json"
    try:
        acknowledge_owner_release(folder, owner, False)
    except ValueError:
        pass
    else:
        raise AssertionError("Unattested owner release accepted")
    acknowledge_owner_release(folder, owner, True)
    return seal["events"] + ["native_exit", "owner_released",
                             "saved_processing_started"]


def main() -> None:
    manifest_path = HERE / "execution-manifest.draft.json"
    manifest = json.loads(manifest_path.read_text())
    command = ("TMPDIR=$PWD/.runtime-work/c129731-test-tmp "
               "SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c129731-output "
               "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/" +
               HERE.name + "/prove_physical_cases.py")
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        construction = json.loads((HERE / entry["construction"]).read_text())
        config = json.loads(next(file["content"] for file in construction["files"]
                                 if file["path"] == "config.json"))
        fixtures = []
        with tempfile.TemporaryDirectory(dir=SCRATCH,
                                         prefix="c129731-physical-") as temporary:
            scratch = Path(temporary)
            for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
                result = physical_fixture(scratch / kind, config, kind)
                result_name = "physical-" + suffix + "-" + kind + ".json"
                log_name = "physical-" + suffix + "-" + kind + ".log"
                write(HERE / result_name, result)
                (HERE / log_name).write_text(
                    "Pinned physical_result: " + entry["case_id"] + " " + kind +
                    " = " + result["physical_checks"]["maneuver"]["status"] +
                    "; synthetic diagnostic fixture; no CARLA acceptance\n")
                fixtures.append({"kind": kind, "command": command,
                                 "exit_code": 0, "log": log_name,
                                 "log_sha256": sha(HERE / log_name),
                                 "result": result_name,
                                 "result_sha256": sha(HERE / result_name)})
            events = lifecycle(scratch / "lifecycle", construction)
        life_name = "physical-" + suffix + "-lifecycle.log"
        (HERE / life_name).write_text(
            "Pinned seal_capture, record_native_exit and owner release ordering; "
            "synthetic fixture has no CARLA resources.\n" +
            " -> ".join(events) + "\n")
        receipt_name = "physical-" + suffix + "-preparation.json"
        write(HERE / receipt_name, {
            "construction_sha256": entry["construction_sha256"],
            "fixtures": fixtures,
            "lifecycle": {"events": events, "exit_code": 0,
                          "log": life_name,
                          "log_sha256": sha(HERE / life_name)}})
        entry["physical_preparation"] = {
            "receipt": receipt_name, "sha256": sha(HERE / receipt_name)}
        print(suffix, "three pinned physical outcomes and ordered lifecycle passed")
    write(manifest_path, manifest)


if __name__ == "__main__":
    main()
