"""Bind exact Native source acquisition and local handoff to all selected cases."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
path = root / "execution-manifest.json"
manifest = json.loads(path.read_text())
channels = ("occupied_lane", "body_intrusion", "protected_motion", "participant_class",
            "four_camera_visibility")
for entry in manifest["cases"]:
    entry["acquisition"] = {
        name: {"entrypoint": "original_capture.py",
               "method": "run_native original 900-frame reviewed lane map and two-actor readback",
               "evidence": "protected-lane-history.jsonl and channel-" + name + ".jsonl"}
        for name in channels}
    entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                               "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}
path.write_text(json.dumps(manifest, indent=2) + "\n")
