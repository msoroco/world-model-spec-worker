"""Bind already run exact-case CPU proofs without changing selected bundles."""

import hashlib
import json
from pathlib import Path

from package_spec import AID, CHANNELS


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind():
    draft = json.loads((HERE / "execution-manifest.selected-draft.json").read_text())
    if draft["assignment_id"] != AID:
        raise ValueError("selected draft identity changed")
    for entry in draft["cases"]:
        suffix = entry["case_id"].removeprefix(AID + "__")
        construction = HERE / entry["construction"]
        if sha(construction) != entry["construction_sha256"]:
            raise ValueError("selected construction changed: " + suffix)
        receipt = HERE / ("proof-compat-receipt-" + suffix + ".json")
        compatibility = json.loads(receipt.read_text())
        if compatibility.get("passed") is not True or compatibility.get("construction_sha256") != sha(construction):
            raise ValueError("selected compatibility proof stale: " + suffix)
        physical = HERE / ("physical-" + suffix + "-receipt.json")
        physical_result = json.loads(physical.read_text())
        if physical_result["construction_sha256"] != sha(construction):
            raise ValueError("physical proof stale: " + suffix)
        saved = HERE / ("proof-selected-saved-" + suffix + ".log")
        saved_result = json.loads(saved.read_text())
        if not all(saved_result.get(key) is True for key in
                   ("passed", "recorded_only", "originals_preserved")):
            raise ValueError("saved replay proof incomplete: " + suffix)
        entry["compatibility"] = {
            "receipt": receipt.name, "sha256": sha(receipt),
            "log": "proof-compat-analysis-" + suffix + ".log",
            "negative_log": "proof-compat-negative-" + suffix + ".log"}
        entry["negative"] = {"log": "proof-compat-negative-" + suffix + ".log"}
        entry["physical_preparation"] = {"receipt": physical.name, "sha256": sha(physical)}
        entry["saved_replay"] = {"log": saved.name, "sha256": sha(saved)}
        entry["post_capture"] = {
            "command": ".venv-cpu/bin/python runtime.py process-saved --manifest work/" + AID +
                       "/execution-manifest.json --case " + entry["case_id"] +
                       " --attempt $ATTEMPT --output $PROCESSED --library runtime/library" +
                       " --validator $LEAN_VALIDATOR --owner-release-receipt $OWNER_RELEASE_RECEIPT",
            "feedback_command": ".venv-cpu/bin/python work/" + AID +
                                "/delivery_audit.py --case " + entry["case_id"] +
                                " --attempt $ATTEMPT --review $PIXEL_REVIEW --physical $PHYSICAL_RESULT",
            "recorded_only": True, "test_exit_code": 0,
            "test_log": saved.name, "test_log_sha256": sha(saved)}
        delivery = HERE / ("delivery-acceptance-" + suffix + ".json")
        entry["delivery_acceptance"] = json.loads(delivery.read_text())
        entry["native_handoff"] = {
            "python_env_var": "CARLA_PYTHON", "host_env_var": "CARLA_HOST",
            "port_env_var": "CARLA_PORT", "reviewed_packet_env_var": "C228989_REVIEWED_PACKET",
            "adapter_module_env_var": "C228989_NATIVE_ADAPTER_MODULE"}
        sources = {
            "ego_control_body": ("pass_native_capture.py", "read_pass_row world vertices"),
            "lane_topology": ("pass_scene.py", "reviewed map and lane source packet"),
            "left_lane_traffic": ("pass_native_capture.py", "per-frame left-lane actor inventory"),
            "ego_lane_and_pass": ("pass_measurements.py", "full-body pass and sampled ego lane"),
            "relative_motion": ("pass_measurements.py", "source-joined longitudinal motion"),
            "camera_frame_identity": ("pass_capture_audit.py", "four-camera full-frame and video decode"),
        }
        entry["acquisition"] = {
            name: {"entrypoint": sources[name][0], "method": sources[name][1],
                   "evidence": "original-source-receipt.json and source-sealed 900-frame trace"}
            for name, _, _ in CHANNELS}
    draft["status"] = "physical_and_selected_proofs_bound_partial"
    output = HERE / "execution-manifest.json"
    output.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n")
    if output.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("manifest exceeds return limit")
    return len(draft["cases"])


if __name__ == "__main__":
    print("bound selected exact CPU proofs:", bind())
