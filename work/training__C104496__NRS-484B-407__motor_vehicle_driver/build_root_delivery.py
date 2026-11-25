"""Author the assignment-level portable dispatch and source observation map."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def main():
    plan_path = HERE / "case-plan.json"
    plan = read(plan_path)
    mapping = plan["source_observation_mapping"]
    if isinstance(mapping, list):
        plan["source_observation_mapping"] = {
            row["term"]: {"evidence": row["measurement"], "channels": row["channels"],
                          "source_refs": row["source_refs"], "uncertainty": row["uncertainty"]}
            for row in mapping
        }
    plan["camera_plan"] = {
        "profile": "overview1080-capability", "duration_s": 35,
        "composition": "synchronized_four_view_primary",
        "coverage": [
            {"view": "overview", "subject": "ego full reversal, other vehicle and both approaches", "interval": "0-35 s"},
            {"view": "approach", "subject": "west incoming lane, ego and other vehicle", "interval": "0-35 s"},
            {"view": "reference_corner", "subject": "east incoming lane and ego body", "interval": "0-35 s"},
            {"view": "driver_reference", "subject": "ego body and road station", "interval": "0-35 s"},
        ],
        "physical_verification_pending": True,
    }
    write(plan_path, plan)
    selected = read(HERE / "selected/probe_01/primary/construction.json")
    config = json.loads(next(row["content"] for row in selected["files"] if row["path"] == "config.json"))
    case_ids = [case["case_id"] for case in plan["cases"]]
    config["supported_case_ids"] = case_ids
    config["selected_case_id"] = None
    config["case"] = None
    config["format"] = "c104496-assignment-dispatch-config-v1"
    write(HERE / "config.json", config)
    runner = '''"""Dispatch one exact C104496 case through the pinned prospective runtime."""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--case", required=True)
    p.add_argument("--candidate", default="primary")
    p.add_argument("--output", required=True)
    p.add_argument("--python", default=os.environ.get("CARLA_PYTHON"))
    p.add_argument("--host", default=os.environ.get("CARLA_HOST", "localhost"))
    p.add_argument("--port", default=os.environ.get("CARLA_PORT", "2000"))
    args = p.parse_args()
    if not args.python:
        raise ValueError("Supply original CARLA Python")
    command = [sys.executable, str(ROOT / "runtime.py"), "capture", "--manifest", str(HERE / "execution-manifest.json"), "--case", args.case, "--candidate", args.candidate, "--output", args.output, "--python", args.python, "--host", args.host, "--port", str(args.port)]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
'''
    (HERE / "runner.py").write_text(runner)
    channels = selected["recording_description"]["channels"]
    names = {row["name"] for row in channels}
    channels.append({"name": "native_map_and_lanes", "unit": "structured", "sampling_rate_hz": 20, "method": "original generated road readback", "time_window": "35 seconds / 700 joined frames", "reference_frame": "generated roadway station", "uncertainty": "original map readback pending"})
    for term, ref in plan["source_observation_mapping"].items():
        if term not in names:
            channels.append({"name": term, "unit": "structured", "sampling_rate_hz": 20,
                             "method": "derived from " + ', '.join(ref["channels"]),
                             "time_window": "35 seconds / 700 joined frames", "reference_frame": "original Native frame",
                             "uncertainty": ref["uncertainty"]})
    construction = {key: selected[key] for key in ("recording_description", "measurement_plan", "static_checks", "termination_rules", "mechanisms")}
    construction.update({"law_id": "NRS-484B-407", "cell_id": "C104496", "actor": "motor_vehicle_driver", "entrypoint": "runner.py", "status": "CPU delivery prepared; original realization pending",
                         "files": [{"path": name, "content": (HERE / name).read_text()} for name in ("runner.py", "config.json")]})
    construction["recording_description"]["channels"] = channels
    write(HERE / "construction.json", construction)


if __name__ == "__main__":
    main()
