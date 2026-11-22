"""Exercise pinned walker completion and capture closure on CPU diagnostics."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
safe = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
if not safe.is_relative_to(REPO/".runtime-work"):
    raise RuntimeError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime imports")
sys.path.insert(0, str(REPO/"runtime/scenario_pipeline"))
from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")


def lines(path, rows):
    Path(path).write_text("".join(json.dumps(row, allow_nan=False)+"\n" for row in rows))


def physical_fixture(root, config, source, kind):
    root.mkdir()
    write(root/"config.json", config)
    all_rows = [json.loads(line) for line in source.read_text().splitlines()]
    body = all_rows if kind != "missing_evidence" else all_rows[:5]
    if kind == "incomplete_motion":
        body = json.loads(json.dumps(body))
        first = sum(point[0] for point in body[0]["body_xy_m"])/4
        for row in body:
            center = sum(point[0] for point in row["body_xy_m"])/4
            shift = first+.1*(center-first)-center
            for point in row["body_xy_m"]:
                point[0] += shift
    lines(root/"trace.jsonl", [{"frame": r["frame"], "time_s": r["time_s"]}
                               for r in body])
    lines(root/"video_frames.jsonl", [{"video_frame": i,
          "carla_frame": r["frame"], "time_s": r["time_s"]}
          for i, r in enumerate(body)])
    if kind != "missing_evidence":
        lines(root/"walker-body-history.jsonl", body)
    write(root/"acquisition-provenance.json", {"provenance_kind": "synthetic_fixture",
                                               "diagnostic_fixture": True})
    result = physical_result(root, {"case_id": config["selected_case_id"],
                                    "target_checks": []})
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[kind]
    if (result["physical_checks"]["maneuver"]["status"] != expected or
            result["maneuver_completed"] != (expected == "met") or
            result["provenance_kind"] != "synthetic_fixture" or
            result["diagnostic_fixture"] is not True):
        raise AssertionError("pinned walker physical result differs: "+kind)
    return result


def lifecycle(root, construction):
    root.mkdir()
    write(root/"construction.json", construction)
    (root/"runner.py").write_text("# synthetic lifecycle source\n")
    lines(root/"trace.jsonl", [{"frame": 0}])
    lines(root/"video_frames.jsonl", [{"carla_frame": 0,
                                      "video_frame": 0, "time_s": 0}])
    write(root/"acquisition-provenance.json", {"provenance_kind": "synthetic_fixture",
                                               "diagnostic_fixture": True})
    try:
        record_native_exit(root)
    except Exception:
        pass
    else:
        raise AssertionError("Native exit accepted before capture closure")
    seal = seal_capture(root, frames=1, restoration={"restored": True}, errors=[],
                        encoder_exit_codes={name: 0 for name in
                        ("overview", "approach", "reference_corner", "driver_reference")})
    record_native_exit(root)
    receipt = root/"owner-release.json"
    try:
        acknowledge_owner_release(root, receipt, False)
    except ValueError:
        pass
    else:
        raise AssertionError("unacknowledged owner release accepted")
    acknowledge_owner_release(root, receipt, True)
    return seal["events"]+["native_exit", "owner_released", "saved_processing_started"]


def main():
    path = HERE/"execution-manifest.json"
    manifest = json.loads(path.read_text())
    command = "SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c143766-physical-runtime PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/"+HERE.name+"/prove_physical_cases.py"
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[1]
        folder = HERE/"cases"/suffix
        construction = json.loads((HERE/entry["construction"]).read_text())
        config = json.loads(next(item["content"] for item in construction["files"]
                                 if item["path"] == "config.json"))
        source = folder/"diagnostic-body-history.jsonl"
        with tempfile.TemporaryDirectory(dir=REPO/".runtime-work",
                                         prefix="c143766-physical-") as temp:
            root = Path(temp)
            fixtures = []
            for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
                result = physical_fixture(root/kind, config, source, kind)
                result_path = folder/("physical-"+kind+".json")
                log_path = folder/("physical-"+kind+".log")
                write(result_path, result)
                log_path.write_text("Pinned physical_result: "+entry["case_id"]+" "+kind+
                                    " = "+result["physical_checks"]["maneuver"]["status"]+
                                    "; synthetic diagnostic only.\n")
                fixtures.append({"kind": kind, "command": command, "exit_code": 0,
                    "log": str(log_path.relative_to(HERE)), "log_sha256": sha(log_path),
                    "result": str(result_path.relative_to(HERE)), "result_sha256": sha(result_path)})
            events = lifecycle(root/"lifecycle", construction)
        life_log = folder/"physical-lifecycle.log"
        life_log.write_text("Pinned closure ordering on synthetic sources; no CARLA resources allocated.\n"+
                            " -> ".join(events)+"\n")
        proof = {"construction_sha256": entry["construction_sha256"],
                 "fixtures": fixtures,
                 "lifecycle": {"events": events, "exit_code": 0,
                               "log": str(life_log.relative_to(HERE)),
                               "log_sha256": sha(life_log)}}
        proof_path = folder/"physical-preparation.json"
        write(proof_path, proof)
        entry["physical_preparation"] = {"receipt": str(proof_path.relative_to(HERE)),
                                         "sha256": sha(proof_path)}
        print(suffix, "three pinned physical outcomes and lifecycle passed")
    write(path, manifest)


if __name__ == "__main__":
    main()
