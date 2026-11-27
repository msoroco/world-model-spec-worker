"""Recorded-only finalizer proof on synthetic original-shaped sources."""
import json
import os
from pathlib import Path
import runpy

from finalize import CHANNELS, finalize
from saved_beam import load_rows


here = Path(__file__).resolve().parent
runpy.run_path(str(here / "prove_compare_beam.py"))
attempt = Path(os.environ["TMPDIR"]).resolve() / "saved-beam-proof"
rows = load_rows(attempt / "beam-rows.jsonl")
trace = []
for row in rows:
    trace.append({"frame": row["native_frame"], "time_s": row["time_s"],
        "position": {"x": row["ego_x_m"], "y": row["ego_y_m"], "z": 0},
        "position_m": [row["ego_x_m"], row["ego_y_m"], 0],
        "heading_deg": 0, "speed_mps": 5, "speed_mph": 5 / .44704,
        "velocity_mps": [5, 0, 0], "control": {}})
(attempt / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in trace))
config = json.loads((attempt / "config.json").read_text())
config.update({"law_id": "NRS-484D-215-1", "cell_id": "C183394",
    "actor": "motor_vehicle_driver", "duration_s": 30, "rate_hz": 20,
    "requested_speed_mps": 2.5, "beam_mode": "dim_within_500",
    "recording_description": {"channels": [{"name": name, "unit": "structured"}
                                           for name in CHANNELS],
                              "context_inputs": [], "limitations": ["diagnostic only"]}})
(attempt / "config.json").write_text(json.dumps(config) + "\n")
(attempt / "acquisition-provenance.json").write_text(json.dumps(
    {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
report = finalize(attempt, attempt / "analysis-report.json")
assert report["legal_compliance"] == "unassessed"
result = json.loads((attempt / "result.json").read_text())
assert result["diagnostic_fixture"] is True
assert result["physical_acceptance_claimed"] is False
assert len(list((attempt / "channels").glob("*.jsonl"))) == len(CHANNELS)
assert all(len(path.read_text().splitlines()) == 600 for path in
           (attempt / "channels").glob("*.jsonl"))
print("PASS: recorded-only beam finalizer, physical assessment and nine channels")
