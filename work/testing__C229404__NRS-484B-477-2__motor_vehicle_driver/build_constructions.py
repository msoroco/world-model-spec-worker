"""Bind each exact alley case and reverse-approach fallback to inline files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def construction(case: dict, config_path: Path) -> dict:
    config = json.loads(config_path.read_text())
    paths = [("config.json", config_path)]
    for name in ("case-plan.json", "runner.py", "analysis.py", "physical_parking.py", "native_capture.py",
                 "finalize_native.py",
                 "carla_alley_adapter.py", "alley_construction.py",
                 "parking_controller.py", "access_measurement.py",
                 "delivery_audit.py", "comparison_audit.py",
                 "measurement-contract.json"):
        paths.append((name, ROOT / name))
    for name in ("test_access_measurement.py", "test_native_capture.py",
                 "test_carla_adapter.py", "test_physical_parking.py"):
        paths.append(("tests/" + name, ROOT / "tests" / name))
    files = [{"path": dest, "source": str(path.relative_to(REPO)),
              "content": path.read_text(encoding="utf-8")} for dest, path in paths]
    return {"law_id": config["law_id"], "cell_id": config["cell_id"],
            "actor": config["actor"], "case_id": case["case_id"],
            "entrypoint": "runner.py", "files": files,
            "recording_description": config["recording_description"],
            "measurement_plan": {"case_id": case["case_id"],
                                 "procedure": "access_measurement.py",
                                 "original_frames": 900,
                                 "source_packets": ["frame_map", "alley_geometry",
                                                    "vehicle_footprint", "activity"],
                                 "legal_blocking_judgment": "unresolved"},
            "static_checks": ["exact identity and case-plan hash",
                              "source-hashed reviewed alley packet and connected ends",
                              "four native camera source joins and original footprint"],
            "termination_rules": ["900 original frames at 20 Hz",
                                  "fail closed on absent Native source or incomplete parked phase"],
            "mechanisms": ["surveyed connected-alley parking target",
                           "route-tracking brake/hold/depart controller",
                           "same-tick four-view original PNG acquisition",
                           "saved original body/access polygon measurement"]}


def main() -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    base = json.loads((ROOT / "config.json").read_text())
    base["plan_sha256"] = hashlib.sha256((ROOT / "case-plan.json").read_bytes()).hexdigest()
    for case in plan["cases"]:
        slug = case["case_id"].removeprefix(plan["assignment_id"] + "__")
        folder = ROOT / "cases" / slug
        for candidate, direction in (("primary", 1), ("fallback1", -1)):
            config = dict(base, selected_case_id=case["case_id"],
                          access_kind=case["access_kind"],
                          parking_position=case["parking_position"],
                          approach_direction=direction)
            config_path = folder / ("config.json" if candidate == "primary"
                                    else "config-fallback1.json")
            write(config_path, config)
            proposal = construction(case, config_path)
            proposal["candidate_id"] = candidate
            filename = "construction.json" if candidate == "primary" else "construction-fallback1.json"
            write(folder / filename, proposal)
            if case is plan["cases"][0] and candidate == "primary":
                write(ROOT / "config.json", config)
                # Rebind the root preview using its own config file.
                write(ROOT / "construction.json", construction(case, ROOT / "config.json"))


if __name__ == "__main__":
    main()
