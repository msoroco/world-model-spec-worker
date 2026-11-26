"""Bind current selected CPU receipts into the exact paved-edge handoff."""

import hashlib
import json
from pathlib import Path

from package_spec import AID, CHANNELS

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    manifest = json.loads((HERE / "execution-manifest.selected-draft.json").read_text())
    if manifest["assignment_id"] != AID or len(manifest["cases"]) != 4:
        raise ValueError("four current-hash selected paved-edge cases required")
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(AID + "__")
        if sha(HERE / entry["construction"]) != entry["construction_sha256"]:
            raise ValueError("selected construction changed")
        compatibility = HERE / ("proof-compat-receipt-" + suffix + ".json")
        physical = HERE / ("physical-" + suffix + "-receipt.json")
        saved = HERE / ("proof-selected-saved-" + suffix + ".log")
        delivery = HERE / ("delivery-acceptance-" + suffix + ".json")
        proof = json.loads(compatibility.read_text())
        if not (proof.get("passed") is True and proof.get("construction_sha256") == entry["construction_sha256"]):
            raise ValueError("selected compatibility proof changed")
        entry["compatibility"] = {"receipt": compatibility.name, "sha256": sha(compatibility),
                                  "log": "proof-compat-analysis-" + suffix + ".log",
                                  "negative_log": "proof-compat-negative-" + suffix + ".log"}
        entry["negative"] = {"log": "proof-compat-negative-" + suffix + ".log"}
        entry["physical_preparation"] = {"receipt": physical.name, "sha256": sha(physical)}
        entry["saved_replay"] = {"log": saved.name, "sha256": sha(saved)}
        entry["post_capture"] = {
            "command": ".venv-cpu/bin/python runtime.py process-saved --manifest work/" + AID +
                       "/execution-manifest.json --case " + entry["case_id"] +
                       " --attempt $ATTEMPT --output $PROCESSED --library runtime/library --validator $LEAN_VALIDATOR --owner-release-receipt $OWNER_RELEASE_RECEIPT",
            "feedback_command": ".venv-cpu/bin/python work/" + AID +
                                "/delivery_audit.py --case " + entry["case_id"] +
                                " --attempt $ATTEMPT --review $PIXEL_REVIEW --physical $PHYSICAL_RESULT",
            "recorded_only": True, "test_exit_code": 0,
            "test_log": saved.name, "test_log_sha256": sha(saved)}
        entry["delivery_acceptance"] = json.loads(delivery.read_text())
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT",
                                   "reviewed_packet_env_var": "C182383_REVIEWED_SITE",
                                   "adapter_module_env_var": "C182383_NATIVE_ADAPTER_MODULE"}
        channel_sources = {
            "paved_surface_classification": ("right_pass.py", "independently sourced public paved surface and adjacent classification"),
            "paved_edge_geometry": ("right_pass_capture.py", "surveyed paved bounds and original body frame join"),
            "ego_and_overtaken_identity": ("right_pass_capture.py", "original Native two-actor identity"),
            "ego_and_overtaken_body_envelopes": ("right_pass_capture.py", "original world body corners projected to road frame"),
            "right_side_pass_event": ("right_pass_envelope.py", "original longitudinal overlap and side readback"),
            "actual_off_pavement_travel": ("right_pass_envelope.py", "measured ego body crossing classified paved edge"),
            "physical_necessity_review": ("right_pass_envelope.py", "zero-clearance lower bound with legal safe alternative unresolved"),
            "vehicle_motion": ("right_pass_capture.py", "original Native position and speed history")}
        entry["acquisition"] = {name: {"entrypoint": channel_sources[name][0],
                                         "method": channel_sources[name][1],
                                         "evidence": "original-source-receipt.json, right-pass-history.json and synchronized 900-frame cameras"}
                                for name, _, _ in CHANNELS}
    manifest["status"] = "physical_and_selected_cpu_proofs_bound_gpu_pending"
    (HERE / "execution-manifest.json").write_text(json.dumps(manifest, indent=2,
                                                               ensure_ascii=False) + "\n")
    return len(manifest["cases"])


if __name__ == "__main__":
    print("bound paved-edge cases:", run())
