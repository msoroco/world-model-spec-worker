"""Bind passed one-way CPU receipts to the assignment delivery manifest."""

import hashlib
import json
from pathlib import Path

from one_way_delivery_audit import ERROR
from one_way_variant import TARGETS


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
PROOFS = HERE / "selected-proofs"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def proof(path):
    path = Path(path)
    return str(path.relative_to(HERE)), digest(path)


def main():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    selected = json.loads((HERE / "one-way-probe-manifest.json").read_text())
    existing = {entry["case_id"]: entry for entry in manifest["cases"]}
    for entry in selected["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        for candidate_id, destination in (("primary", entry),
                                          ("fallback1", entry["candidates"][0])):
            stem = suffix + "-" + candidate_id
            offline = PROOFS / (stem + "-offline.log")
            destination["offline"] = {"command":
                ".venv-cpu/bin/python -B runtime.py offline --manifest work/" +
                ASSIGNMENT + "/one-way-probe-manifest.json --case " + case_id +
                " --candidate " + candidate_id + " --output .runtime-work/c313130_oneway_offline_" +
                suffix + "_" + candidate_id + " --python $PWD/.venv-cpu/bin/python",
                "exit_code": 0, "construction_sha256": destination["construction_sha256"],
                "log": proof(offline)[0], "log_sha256": digest(offline)}
            receipt = PROOFS / (stem + "-compatibility.json")
            public = json.loads(receipt.read_text())
            if (public["case_id"] != case_id or
                    public["construction_sha256"] != destination["construction_sha256"] or
                    public["passed"] is not True):
                raise ValueError("One-way compatibility receipt differs: " + stem)
            destination["compatibility"] = {
                "receipt": proof(receipt)[0], "sha256": digest(receipt),
                "log": proof(PROOFS / (stem + "-analysis.log"))[0],
                "negative_log": proof(PROOFS / (stem + "-negative.log"))[0]}
            if candidate_id == "primary":
                entry["negative"] = {"log": destination["compatibility"]["negative_log"]}
        processing = PROOFS / (suffix + "-primary-processing.json")
        saved = json.loads(processing.read_text())
        if (saved["case_id"] != case_id or saved["passed"] is not True or
                saved["missing_evidence"] or not saved["recorded_only"]):
            raise ValueError("One-way saved-only receipt differs")
        entry["saved_processing"] = {"receipt": proof(processing)[0],
                                     "sha256": digest(processing)}
        entry["post_capture"] = {"command":
            "python runtime.py process-saved --manifest work/" + ASSIGNMENT +
            "/execution-manifest.json --case " + case_id +
            " --attempt \"$ATTEMPT\" --output \"$SAVED_OUTPUT\" --library runtime/library --validator \"$DECODER\"",
            "feedback_command": "cat \"$SAVED_OUTPUT\"/v0001/feedback.json",
            "recorded_only": True, "test_exit_code": 0,
            "test_log": proof(processing)[0], "test_log_sha256": digest(processing)}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
            "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}
        entry["acquisition"] = {name: {"entrypoint": "one_way_capture.py",
            "method": "20 Hz original Native one-way tunnel direction, portal, body and four-camera acquisition",
            "evidence": "tunnel-context.json, road-direction-survey.json, tunnel-rows.jsonl, trace.jsonl, video_frames.jsonl and four original videos"}
            for name in ("st.elevated_structure", "drv.approaching", "rel.centre_distance",
                         "st.sight_distance", "drv.sight_distance_adequate", "st.centre_line",
                         "rel.occupies", "st.one_way_roadway")}
        physical = HERE / ("physical-preparation-" + suffix + ".json")
        entry["physical_preparation"] = {"case_id": case_id,
            "receipt": physical.name, "sha256": digest(physical)}
        positive = PROOFS / (suffix + "-delivery-audit.log")
        negative = PROOFS / (suffix + "-delivery-negative.log")
        entry["delivery_acceptance"] = {"case_id": case_id, "sets": ["full-train"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "script": "one_way_delivery_audit.py",
            "script_sha256": digest(HERE / "one_way_delivery_audit.py"),
            "command": ".venv-cpu/bin/python -B work/" + ASSIGNMENT +
                "/one_way_delivery_audit.py --case " + case_id + " --diagnostic",
            "negative_command": ".venv-cpu/bin/python -B work/" + ASSIGNMENT +
                "/one_way_delivery_audit.py --case " + case_id,
            "test_exit_code": 0, "negative_exit_code": 1,
            "negative_expected_error": ERROR,
            "test_log": proof(positive)[0], "test_log_sha256": digest(positive),
            "negative_log": proof(negative)[0], "negative_log_sha256": digest(negative),
            "scope": "CPU diagnostic join and required rejection; original Native physical and legal acceptance pending"}
        existing[case_id] = entry
    manifest["cases"] = list(existing.values())
    manifest["status"] = "selected_delivery_cpu_prepared_full_statutory_review_pending"
    path = HERE / "execution-manifest.json"
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"cases": len(manifest["cases"]),
                      "manifest_sha256": digest(path)}))


if __name__ == "__main__":
    main()
