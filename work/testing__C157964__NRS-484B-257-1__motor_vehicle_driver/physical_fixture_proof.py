"""Exercise source-bound physical completion and ownership closure on CPU fixtures."""

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release

CASES = ("officer_active_stop_then_go", "officer_active_hold",
         "officer_present_inactive", "no_officer_yield_nearest_view")
STATUS = {"complete_motion": "met", "incomplete_motion": "not_met",
          "missing_evidence": "unverified"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def run(suffix, kind, output):
    if suffix not in CASES or kind not in (*STATUS, "lifecycle"):
        raise ValueError("Unknown exact physical fixture")
    case_id = HERE.name + "__" + suffix
    manifest = json.loads((HERE / "execution-manifest-draft.json").read_text())
    entry = next(e for e in manifest["cases"] if e["case_id"] == case_id)
    construction = json.loads((HERE / entry["construction"]).read_text())
    config = json.loads(next(f["content"] for f in construction["files"] if f["path"] == "config.json"))
    spec = json.loads((HERE / (suffix + "-diagnostic-sources.json")).read_text())
    source = spec["files"]
    with tempfile.TemporaryDirectory(prefix="c157964-physical-") as temporary:
        root = Path(temporary)
        write(root / "config.json", config)
        for name in ("officer_context.json", "officer_history.jsonl", "trace.jsonl", "video_frames.jsonl"):
            (root / name).write_text(source[name])
        write(root / "acquisition-provenance.json", {"provenance_kind": "synthetic_fixture",
                                                       "diagnostic_fixture": True,
                                                       "physical_acceptance_claimed": False})
        if kind == "lifecycle":
            saved = json.loads((HERE / ("saved-processing-" + suffix + ".log")).read_text())
            if (saved.get("passed") is not True or saved.get("recorded_only") is not True
                    or saved.get("analysis_revision", {}).get("construction_sha256") != entry["construction_sha256"]):
                raise ValueError("Selected saved-only CPU replay is stale")
            write(root / "construction.json", construction)
            (root / "runner.py").write_text(next(f["content"] for f in construction["files"] if f["path"] == "runner.py"))
            write(root / "acquisition-provenance.json", {"provenance_kind": "native",
                                                           "diagnostic_fixture": True,
                                                           "physical_acceptance_claimed": False,
                                                           "scope": "Synthetic ownership lifecycle CPU fixture only"})
            sealed = seal_capture(root, frames=600, restoration={"restored": True, "fixture_only": True},
                                  errors=[], encoder_exit_codes={"diagnostic_encoder": 0})
            exited = record_native_exit(root)
            released = acknowledge_owner_release(root, root / "owner-release.json", True)
            events = sealed["events"] + [exited["event"], released["event"], saved["events"][0]]
            if events != ["capture_finished", "encoders_closed", "restoration_verified",
                          "native_exit", "owner_released", "saved_processing_started"]:
                raise ValueError("Saved processing began before ownership closure")
            report = {"events": events, "diagnostic_fixture": True,
                      "capture_seal_sha256": sha(root / "capture-seal.json"),
                      "native_exit_sha256": sha(root / "native-exit.json"),
                      "owner_release_sha256": sha(root / "owner-release.json")}
            write(output, report)
            print(json.dumps({"case_id": case_id, "kind": kind, "events": events,
                              "physical_acceptance_claimed": False}, sort_keys=True))
            return
        source_rows = [json.loads(line) for line in source["officer_history.jsonl"].splitlines()]
        source_frames = [json.loads(line) for line in source["video_frames.jsonl"].splitlines()]
        rows, frames = [], []
        for index, x in enumerate((-15, 0, 12, 16)):
            row = json.loads(json.dumps(source_rows[-1]))
            row["frame"] = 100 + index
            row["time_s"] = 5 + index / 20
            row["ego"]["body_vertices_xy_m"] = [[x-1, -1], [x-1, 1], [x+1, 1], [x+1, -1]]
            frame = json.loads(json.dumps(source_frames[-1]))
            frame["carla_frame"] = row["frame"]
            frame["time_s"] = row["time_s"]
            frame["video_frame"] = index
            frame["camera_frames"] = {name: row["frame"] for name in
                                       ("overview", "approach", "reference_corner", "driver_reference")}
            rows.append(row)
            frames.append(frame)
        if kind == "incomplete_motion":
            for row in rows:
                row["ego"]["body_vertices_xy_m"] = [[-16, -1], [-16, 1], [-14, 1], [-14, -1]]
        (root / "officer_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(frame) + "\n" for frame in frames))
        if kind == "missing_evidence":
            (root / "officer_history.jsonl").unlink()
        result = physical_result(root, {"target_checks": [], "realized_observables": {},
                                        "setup_confirmed": False, "behavior_attempted": False,
                                        "maneuver_completed": False})
        status = result["physical_checks"]["maneuver"]["status"]
        if (status != STATUS[kind] or result.get("maneuver_completed") != (status == "met")
                or result.get("provenance_kind") != "synthetic_fixture"
                or result.get("diagnostic_fixture") is not True
                or result.get("physical_acceptance_claimed") is not False):
            raise ValueError("Pinned physical checker returned wrong diagnostic state")
        if status == "met" and not result.get("realized_observables"):
            raise ValueError("Complete diagnostic fixture lacks measured motion")
        write(output, result)
        print(json.dumps({"case_id": case_id, "kind": kind, "status": status,
                          "physical_acceptance_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--kind", choices=(*STATUS, "lifecycle"), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.case, args.kind, args.output)
