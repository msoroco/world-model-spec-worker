"""Bind original acquisition sources and exact Native handoff to rail cases."""

import json
from pathlib import Path

WORK = Path(__file__).resolve().parents[1]
MANIFEST = WORK / "execution-manifest.json"

SOURCES = {
    "st.railway_crossing": ["road.xodr", "rail-body.jsonl", "original-source-review/railway.json"],
    "drv.approaching": ["rail-body.jsonl", "trace.jsonl"],
    "st.sight_distance": ["rail-rays.jsonl", "rail-body.jsonl", "original-source-review/approach.json"],
    "rel.visible": ["rail-rays.jsonl", "video_frames.jsonl"],
    "kin.speed": ["rail-body.jsonl", "trace.jsonl"],
    "ru.rail_vehicle": ["rail-rays.jsonl", "original-source-review/railway.json"],
    "dev.human_direction": ["reviewed-exceptions.jsonl", "original-source-review/flagman.json"],
    "dev.railway_signal_or_gate": ["reviewed-exceptions.jsonl", "original-source-review/signal.json"],
    "rel.centre_distance": ["rail-body.jsonl", "road.xodr"],
}


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}
        entry["acquisition"] = {
            name: {"entrypoint": "runner.py",
                   "method": "original Native frame acquisition and independent source review; "+name,
                   "evidence": evidence}
            for name, evidence in SOURCES.items()
        }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print("bound original acquisition and Native handoff", len(manifest["cases"]))


if __name__ == "__main__":
    main()
