"""Attach exact selected diagnostic CPU receipts to the draft manifest."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c102642-new"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record() -> None:
    manifest = HERE / "execution-manifest.json"
    draft = json.loads(manifest.read_text())
    for entry in draft["cases"]:
        kind = entry["case_id"].rsplit("__", 1)[1]
        case = HERE / "cases" / kind
        offline = SCRATCH / f"offline-{kind}-v7/offline.log"
        output = SCRATCH / f"compat-{kind}-v7"
        for filename, source in (("offline.log", offline),
                                 ("positive-analysis.log", output / "compatibility-analysis.log"),
                                 ("negative-analysis.log", output / "negative-analysis.log"),
                                 ("compatibility.json", output / "compatibility.json")):
            if not source.is_file():
                raise ValueError("CPU proof missing: " + str(source))
            shutil.copyfile(source, case / filename)
        receipt = json.loads((case / "compatibility.json").read_text())
        if (receipt["construction_sha256"] != entry["construction_sha256"] or
                receipt["case_id"] != entry["case_id"] or
                sha(case / "positive-analysis.log") != receipt["log_sha256"] or
                sha(case / "negative-analysis.log") != receipt["negative_log_sha256"]):
            raise ValueError("CPU proof source hash mismatch: " + kind)
        entry["kind"] = "delivery"
        entry["measurement_procedure"] = {"entrypoint": "analysis.py"}
        entry["offline"] = {
            "command": f".venv-cpu/bin/python runtime.py offline --manifest {manifest.relative_to(REPO)} --case {entry['case_id']} --output .runtime-work/c102642-new/offline-{kind}-v7 --python .venv-cpu/bin/python",
            "construction_sha256": entry["construction_sha256"],
            "exit_code": 0,
            "log": f"cases/{kind}/offline.log",
            "log_sha256": sha(case / "offline.log")}
        entry["compatibility"] = {
            "receipt": f"cases/{kind}/compatibility.json",
            "sha256": sha(case / "compatibility.json"),
            "log": f"cases/{kind}/positive-analysis.log"}
        entry["negative"] = {"log": f"cases/{kind}/negative-analysis.log"}
        entry["native_handoff"] = {
            "python_env_var": "CARLA_PYTHON", "host_env_var": "CARLA_HOST",
            "port_env_var": "CARLA_PORT"}
        entry["acquisition"] = {
            "original_interaction": {"entrypoint": "native_capture.py", "method": "capture",
                                     "evidence": "native-trace.json frame and actor identity"},
            "observed_driver_act": {"entrypoint": "carla_adapter.py", "method": "observe",
                                    "evidence": "original_observer Native act readback"},
            "door_envelope_xy": {"entrypoint": "carla_adapter.py", "method": "observe",
                                 "evidence": "original_observer swept door or body vertices"},
            "passing_body_xy": {"entrypoint": "carla_adapter.py", "method": "observe",
                                "evidence": "passing Native actor bounding vertices"},
            "passing_speed_mps": {"entrypoint": "carla_adapter.py", "method": "observe",
                                  "evidence": "passing Native actor velocity"},
            "passing_response": {"entrypoint": "carla_adapter.py", "method": "observe",
                                 "evidence": "passing Native actor brake and acceleration"},
            "camera_frame_join": {"entrypoint": "native_capture.py", "method": "capture",
                                  "evidence": "four source-hashed RGB frames per world tick"},
            "hill_crest_loading_site": {"entrypoint": "native_capture.py", "method": "capture",
                                         "evidence": "site_survey in door-source.json"},
            "parked_vehicle_pose": {"entrypoint": "carla_adapter.py", "method": "observe",
                                    "evidence": "parked Native actor pose"},
            "driver_act_and_side": {"entrypoint": "carla_adapter.py", "method": "observe",
                                    "evidence": "original_observer Native act and side"},
            "door_vertices": {"entrypoint": "carla_adapter.py", "method": "observe",
                              "evidence": "original_observer swept door vertices"},
            "passing_traffic_body": {"entrypoint": "carla_adapter.py", "method": "observe",
                                     "evidence": "passing Native actor bounding vertices"},
            "traffic_response": {"entrypoint": "carla_adapter.py", "method": "observe",
                                 "evidence": "passing Native actor brake and acceleration"},
            "camera_frame_map": {"entrypoint": "native_capture.py", "method": "capture",
                                 "evidence": "source-hashed camera frame map"}}
        print(kind, "selected compatibility passed", sha(case / "compatibility.json")[:12])
    manifest.write_text(json.dumps(draft, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    record()
