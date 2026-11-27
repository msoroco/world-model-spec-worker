"""Retain exact CPU receipts and bind the selected Native handoff."""

import hashlib
import json
from pathlib import Path
import shutil


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PROOFS = HERE / "selected-proofs"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return {"path": str(target.relative_to(HERE)), "sha256": sha(target)}


def main():
    manifest = json.loads((HERE / "selected-probe-manifest.json").read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        for candidate_id, destination in [("primary", entry),
                                          ("fallback1", entry["candidates"][0])]:
            stem = suffix + "-" + candidate_id
            offline_path = REPO / ".runtime-work" / ("c313130_offline_final_" +
                suffix + "_" + candidate_id) / "offline.log"
            offline = copy(offline_path, PROOFS / (stem + "-offline.log"))
            destination["offline"] = {"command": ".venv-cpu/bin/python -B runtime.py offline --manifest " +
                str((HERE / "selected-probe-manifest.json").relative_to(REPO)) +
                " --case " + entry["case_id"] + " --candidate " + candidate_id +
                " --output .runtime-work/c313130_offline_final_" + suffix + "_" + candidate_id +
                " --python $PWD/.venv-cpu/bin/python", "exit_code": 0,
                "construction_sha256": destination["construction_sha256"],
                "log": offline["path"], "log_sha256": offline["sha256"]}
            source = REPO / ".runtime-work" / ("c313130_compat_final_" +
                suffix + "_" + candidate_id)
            public = copy(source / "compatibility.json", PROOFS / (stem + "-compatibility.json"))
            analysis = copy(source / "compatibility-analysis.log", PROOFS / (stem + "-analysis.log"))
            negative = copy(source / "negative-analysis.log", PROOFS / (stem + "-negative.log"))
            destination["compatibility"] = {"receipt": public["path"],
                "sha256": public["sha256"], "log": analysis["path"],
                "negative_log": negative["path"]}
            if candidate_id == "primary":
                destination["negative"] = {"log": negative["path"]}
        processing = copy(REPO / ".runtime-work" / ("c313130_saved_final_" + suffix) /
            "v0001/processing.json", PROOFS / (suffix + "-primary-processing.json"))
        entry["saved_processing"] = {"receipt": processing["path"],
            "sha256": processing["sha256"]}
        entry["post_capture"] = {"command": "python runtime.py process-saved --manifest work/" +
            HERE.name + "/execution-manifest.json --case " + entry["case_id"] +
            " --attempt \"$ATTEMPT\" --output \"$SAVED_OUTPUT\" --library runtime/library --validator \"$DECODER\"",
            "feedback_command": "cat \"$SAVED_OUTPUT\"/v0001/feedback.json",
            "recorded_only": True, "test_exit_code": 0,
            "test_log": processing["path"], "test_log_sha256": processing["sha256"]}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
            "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}
        entry["acquisition"] = {name: {"entrypoint": "native_capture.py",
            "method": "20 Hz original Native tunnel portal, body, lane and four-camera acquisition",
            "evidence": "tunnel-context.json, tunnel-rows.jsonl, trace.jsonl, video_frames.jsonl and four original videos"}
            for name in ("st.elevated_structure", "drv.approaching", "rel.centre_distance",
                "st.sight_distance", "drv.sight_distance_adequate", "st.centre_line",
                "rel.occupies", "st.one_way_roadway")}
        physical = HERE / ("physical-preparation-" + suffix + ".json")
        entry["physical_preparation"] = {"case_id": entry["case_id"],
            "receipt": physical.name, "sha256": sha(physical)}
    manifest["status"] = "selected_delivery_cpu_prepared"
    (HERE / "execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"execution_manifest_sha256": sha(HERE / "execution-manifest.json")}))


if __name__ == "__main__":
    main()
