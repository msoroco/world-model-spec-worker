"""Materialize two exact source-bound obstruction constructions."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NATIVE = ROOT / "native"
ASSIGNMENT = "training__C135702__NRS-484B-450-1k__motor_vehicle_driver"
CODE = ("runner.py", "geometry.py", "measure_obstruction.py", "source_join.py", "finalize.py")
CASE_IDS = [ASSIGNMENT + "__selected_dacdf461__condition_" + suffix for suffix in "ab"]


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def recording_description() -> dict:
    descriptions = {
        "drv.standing_or_parked": "same-frame ego rest and operator activity source",
        "st.obstruction": "original barrier bodies and road XY",
        "rel.bearing": "ego to physical-obstruction center bearing",
        "rel.centre_distance": "ego to physical-obstruction center distance",
        "st.lane_width": "original highway width and sampled free opening",
        "drv.hard_deceleration": "passing vehicle speed difference, engineering only",
        "kin.velocity": "same-frame ego and passing vehicle velocity",
        "drv.forced_halt": "original traffic-conflict source review",
    }
    return {"channels": [{"name": name, "unit": "structured", "sampling_rate_hz": 20,
                           "method": method, "time_window": "600 original frames",
                           "reference_frame": "Native world and reviewed source context",
                           "uncertainty": "Original realization and legal applicability require review"}
                          for name, method in descriptions.items()],
            "context_inputs": [{"name": "exception_authority", "unit": "structured",
                                "method": "original source records and copied SHA256 bindings"}],
            "limitations": ["Barrier bodies represent a physical obstruction, not a source-proven excavation.",
                            "Fixtures do not establish actual traffic response or legal obstruction."]}


def build() -> None:
    description = recording_description()
    files = {name: (NATIVE / name).read_text() for name in CODE}
    files["tests/test_bundle.py"] = (ROOT / "tests/test_bundle.py").read_text()
    for index, suffix in enumerate("ab"):
        cfg = json.loads((NATIVE / ("config-condition_" + suffix + ".json")).read_text())
        cfg["supported_case_ids"] = CASE_IDS
        cfg["selected_case_id"] = CASE_IDS[index]
        cfg["required_atoms"] = []
        cfg["source_packets"] = []
        cfg["recording_description"] = description
        for candidate in ("primary", "fallback1"):
            selected = dict(cfg)
            if candidate == "fallback1":
                selected["passing_throttle"] = .35
                selected["brake_station_x_m"] = -15
            entries = [{"path": name, "content": content} for name, content in files.items()]
            entries.append({"path": "config.json", "content": json.dumps(selected, indent=2) + "\n"})
            construction = {"case_id": CASE_IDS[index], "law_id": "NRS-484B-450-1k",
                        "cell_id": "C135702", "actor": "motor_vehicle_driver",
                        "entrypoint": "runner.py", "files": entries,
                        "measurement_plan": {"entrypoint": "finalize.py",
                                             "required_sources": ["native_samples.jsonl", "camera-frames.jsonl",
                                                                  "exception-context.json", "obstruction-inventory.json",
                                                                  "road.xodr", "video_frames.jsonl"],
                                             "source_review_required": True},
                        "recording_description": description,
                        "static_checks": ["exact NRS 484B.450(1)(k) identity and physical obstruction",
                                          "two parked positions with same fixed highway and barrier plan",
                                          "600 original frames at 20 Hz with four synchronized cameras"],
                        "termination_rules": ["600 original frames", "restore Native world and owned actors"],
                        "mechanisms": ["authored two-lane OpenDRIVE highway and three spawned barrier assets",
                                       "two motor-vehicle actors with same-frame body and speed readback",
                                       "separate hash-bound authority source review"],
                        "status": "selected_native_cpu_draft_original_capture_pending"}
            if index == 0 and candidate == "primary":
                for name, content in files.items():
                    destination = ROOT / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(content)
                _write(ROOT / "config.json", selected)
                _write(ROOT / "construction.json", construction)
            else:
                relative = ("cases/condition_" + suffix + "/" +
                            ("construction.json" if candidate == "primary" else "fallback1-construction.json"))
                _write(ROOT / relative, construction)


if __name__ == "__main__":
    build()
