"""Exercise positive and missing-original-source analysis on a synthetic packet."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from nearest_view import REQUIRED_SOURCES


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / ".runtime-work" / "c158196-source-analysis"


def build_packet() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    sources = {}
    for name in REQUIRED_SOURCES:
        path = OUT / "source" / (name + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"synthetic_diagnostic": name}) + "\n")
        sources[name] = {"path": str(path.relative_to(OUT)),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    frames = [{"frame": 100 + i, "time_s": 5 + i / 20,
               "ego_front_station_m": float(i), "ego_speed_mps": 2.0 if i < 3 else 0.4,
               "through_center_station_m": 20.0 - i,
               "view_clear": i >= 2, "through_occupied": i >= 4,
               "ego_within_intersection": i >= 4}
              for i in range(7)]
    packet = {"context": {"cell_id": "C158196", "law_id": "NRS-484B-257-1",
                          "proper_yield_sign": True, "through_highway": True,
                          "connected_approach": True, "marked_stop_line": False,
                          "near_side_crosswalk": False, "sidewalk_derived_crosswalk": False,
                          "officer_controlling": False, "signal_controlling": False,
                          "nearest_view_station_m": 2.0,
                          "intersection_entry_station_m": 4.0},
              "sources": sources, "frames": frames,
              "diagnostic_scope": "synthetic CPU interface proof, not Native evidence"}
    location = OUT / "packet.json"
    location.write_text(json.dumps(packet, indent=2) + "\n")
    return location


def main() -> None:
    source = build_packet()
    command = [sys.executable, str(HERE / "nearest_view.py"), str(source),
               str(OUT / "measurement.json")]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    positive = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    (HERE / "cpu-source-positive.log").write_text(
        f"command: {' '.join(command)}\nexit: {positive.returncode}\n"
        + positive.stdout + positive.stderr + "synthetic source packet verified\n")
    if positive.returncode:
        raise ValueError("positive source analysis failed")
    measured = json.loads((OUT / "measurement.json").read_text())["measurement"]
    if measured["first_view_frame"] != 102 or measured["first_entry_frame"] != 104:
        raise ValueError("wrong source measurement")
    (OUT / "source" / "view_raycast.json").unlink()
    negative = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    (HERE / "cpu-source-negative.log").write_text(
        f"command: {' '.join(command)}\nexit: {negative.returncode}\n"
        + negative.stdout + negative.stderr)
    if negative.returncode == 0 or "view_raycast source bytes missing" not in negative.stderr:
        raise ValueError("missing-source negative analysis did not reject")
    print("positive source analysis and missing-source rejection passed")


if __name__ == "__main__":
    main()
