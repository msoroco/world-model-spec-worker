"""Bind four structure case CPU receipts into the canonical handoff."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PROOFS = HERE / "selected-proofs"
CHANNELS = ("st.elevated_structure", "drv.approaching", "rel.centre_distance",
            "st.sight_distance", "drv.sight_distance_adequate", "st.centre_line",
            "rel.occupies", "st.one_way_roadway")
ATOMS = ("kin.position", "kin.heading", "rel.occupies")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind():
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    structural = json.loads((HERE / "structure-probe-manifest.json").read_text())
    current = {case["case_id"]: case for case in manifest["cases"]}
    for entry in structural["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        if case_id in current:
            raise ValueError("Structure case already bound: " + case_id)
        for candidate_id, destination in (("primary", entry),
                                          ("fallback1", entry["candidates"][0])):
            stem = suffix + "-" + candidate_id
            offline = PROOFS / (stem + "-offline.log")
            public = PROOFS / (stem + "-compatibility.json")
            analysis = PROOFS / (stem + "-analysis.log")
            negative = PROOFS / (stem + "-negative.log")
            receipt = json.loads(public.read_text())
            if (receipt.get("case_id") != case_id or
                    receipt.get("candidate_id") != candidate_id or
                    receipt.get("construction_sha256") != destination["construction_sha256"] or
                    receipt.get("log_sha256") != sha(analysis) or
                    receipt.get("negative_log_sha256") != sha(negative)):
                raise ValueError("Stale structure public proof: " + stem)
            offline_output = ".runtime-work/c313130-structure-offline-" + stem
            if stem == "bridge_right-primary":
                offline_output = ".runtime-work/c313130-structure-bridge-right-offline-3"
            destination["offline"] = {"command": ".venv-cpu/bin/python runtime.py offline --manifest work/" +
                HERE.name + "/structure-probe-manifest.json --case " + case_id +
                " --candidate " + candidate_id + " --output " + offline_output +
                " --python $PWD/.venv-cpu/bin/python", "exit_code": 0,
                "construction_sha256": destination["construction_sha256"],
                "log": "selected-proofs/" + offline.name, "log_sha256": sha(offline)}
            destination["compatibility"] = {"receipt": "selected-proofs/" + public.name,
                "sha256": sha(public), "log": "selected-proofs/" + analysis.name,
                "negative_log": "selected-proofs/" + negative.name}
            if candidate_id == "primary":
                destination["negative"] = {"log": "selected-proofs/" + negative.name}
        processing = PROOFS / (suffix + "-primary-processing.json")
        saved = json.loads(processing.read_text())
        if saved.get("case_id") != case_id or not saved.get("passed"):
            raise ValueError("Stale structure saved proof: " + suffix)
        entry["saved_processing"] = {"receipt": "selected-proofs/" + processing.name,
            "sha256": sha(processing)}
        entry["post_capture"] = {"command": "python runtime.py process-saved --manifest work/" +
            HERE.name + "/execution-manifest.json --case " + case_id +
            " --attempt \"$ATTEMPT\" --output \"$SAVED_OUTPUT\" --library runtime/library --validator \"$DECODER\"",
            "feedback_command": "cat \"$SAVED_OUTPUT\"/v0001/feedback.json",
            "recorded_only": True, "test_exit_code": 0,
            "test_log": "selected-proofs/" + processing.name,
            "test_log_sha256": sha(processing)}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
            "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}
        entry["acquisition"] = {name: {"entrypoint": "structure_capture.py",
            "method": "20 Hz original Native raised deck, supports, body, lane, sight and four-camera acquisition",
            "evidence": "structure-context.json, structure-rows.jsonl, trace.jsonl, video_frames.jsonl and four original videos"}
            for name in dict.fromkeys(CHANNELS + ATOMS)}
        physical = HERE / ("structure-physical-preparation-" + suffix + ".json")
        entry["physical_preparation"] = {"case_id": case_id,
            "receipt": physical.name, "sha256": sha(physical)}
        manifest["cases"].append(entry)
    manifest["status"] = "selected_delivery_cpu_prepared"
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    return {"cases": len(manifest["cases"]), "sha256": sha(path)}


if __name__ == "__main__":
    print(json.dumps(bind()))
