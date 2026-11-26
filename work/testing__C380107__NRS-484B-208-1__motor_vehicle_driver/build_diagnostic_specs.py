"""Build bounded synthetic CPU fixtures for compatibility, never Native evidence."""

import hashlib
import json
from pathlib import Path

from hov_controls import selected_schedule
from package_contract import ASSIGNMENT

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASE = REPO / "work/testing__C422976__LVMC-11-46-030__motor_vehicle_driver/cases/no_warning_travel/diagnostic-spec.json"
BASE_MAP = REPO / "work/testing__C422976__LVMC-11-46-030__motor_vehicle_driver/diagnostic-map.xodr"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")


def diagnostic_rows(case):
    case_id = case["case_id"]
    schedule = selected_schedule(case_id, 9.0)
    suffix = case_id.rsplit("__", 1)[-1]
    ego_speed = schedule["ego_target_speed_mps"]
    rear_speed = schedule["rear_target_speed_mps"]
    if suffix == "speed_at_limit":
        ego_speed, rear_speed = 9.0, 11.0
    rows = []
    for frame in range(900):
        time_s = frame / 20
        gap = 75.0 - (rear_speed - ego_speed) * time_s
        lane = "L0" if suffix != "move_right" or frame < 240 else "L1"
        rows.append({"frame": frame, "time_s": time_s,
                     "ego_lane_id": lane, "rear_lane_id": "L0",
                     "ego_speed_mps": ego_speed, "rear_speed_mps": rear_speed,
                     "rear_to_ego_signed_gap_m": gap,
                     "sign_present_readback": frame >= schedule["sign_exposure_start_frame"]})
    return rows


def main():
    base = json.loads(BASE.read_text(encoding="utf-8"))
    map_bytes = BASE_MAP.read_bytes()
    (HERE / "diagnostic-map.xodr").write_bytes(map_bytes)
    proposal = json.loads((HERE / "proposals/cases.json").read_text(encoding="utf-8"))
    cases = [c for c in proposal["cases"] if c.get("target_law_id")]
    if len(cases) != 18:
        raise ValueError("exact 18-case diagnostic selection required")
    for case in cases:
        case_id = case["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        data = json.loads(json.dumps(base))
        rows = diagnostic_rows(case)
        schedule = selected_schedule(case_id, 9.0)
        context = {"assignment_id": ASSIGNMENT, "case_id": case_id, "diagnostic_fixture": True,
                   "same_direction_lane_ids": ["L0", "L1"], "extreme_left_lane_id": "L0",
                   "posted_limit_mps": 9.0, "hov_designation_state": schedule["hov_designation_request"],
                   "hov_compliance_state": schedule["hov_compliance_request"],
                   "original_hov_occupancy_count": schedule["hov_occupancy_target"],
                   "exception_context_request": schedule["exception_context_request"]}
        for name in ("controlled_access_source", "lane_marking_source", "extreme_left_lane_source",
                     "posted_limit_source", "geographical_boundary_source", "driver_identity_source",
                     "motor_vehicle_source", "hov_designation_source", "hov_hours_source",
                     "hov_occupancy_rule_source", "hov_access_source", "hov_sign_source",
                     "hov_vehicle_category_source", "hov_compliance_source", "knowledge_circumstances_source",
                     "other_exceptions_source"):
            context[name] = "synthetic CPU fixture; no original authority"
        data["files"]["context.json"] = json.dumps(context, separators=(",", ":")) + "\n"
        data["files"]["trace.json"] = json.dumps({"case_id": case_id, "diagnostic_fixture": True,
                                                    "frames": rows}, separators=(",", ":")) + "\n"
        data["files"]["site.json"] = json.dumps({"diagnostic_fixture": True,
            "reviewed_original_site": False, "case_id": case_id}, separators=(",", ":")) + "\n"
        motion = []
        evidence = []
        for row, line in zip(rows, data["files"]["trace.jsonl"].splitlines()):
            value = json.loads(line)
            x = 55.0 + row["ego_speed_mps"] * (row["frame"] + 1) / 20
            y = 0.0 if row["ego_lane_id"] == "L0" else 3.5
            value.update(position_m=[x, y, 0], position={"x": x, "y": y, "z": 0},
                         speed_mps=row["ego_speed_mps"],
                         speed_mph=row["ego_speed_mps"] * 2.2369362921,
                         velocity_mps=[row["ego_speed_mps"], 0, 0])
            motion.append(json.dumps(value, separators=(",", ":")))
        data["files"]["trace.jsonl"] = "\n".join(motion) + "\n"
        for row, line in zip(rows, data["files"]["capture/evidence.jsonl"].splitlines()):
            value = json.loads(line)
            x = 55.0 + row["ego_speed_mps"] * (row["frame"] + 1) / 20
            y = 0.0 if row["ego_lane_id"] == "L0" else 3.5
            value["ego"]["position_m"] = [x, y, 0]
            value["ego"]["speed_mps"] = row["ego_speed_mps"]
            value["ego"]["body_vertices_m"] = [[x + dx, y + dy, z]
                for dx in (-2.0, 2.0) for dy in (-.8, .8) for z in (0, 1.5)]
            evidence.append(json.dumps(value, separators=(",", ":")))
        data["files"]["capture/evidence.jsonl"] = "\n".join(evidence) + "\n"
        data["files"]["capture/recorder_info.txt"] = "Create 11: vehicle.test (synthetic C380107 highway)\n"
        manifest = json.loads(data["files"]["capture/manifest.json"])
        manifest["case_id"] = case_id
        manifest["sources"] = {"road.xodr": sha(map_bytes),
                               "trace.jsonl": sha(data["files"]["trace.jsonl"].encode())}
        data["files"]["capture/manifest.json"] = json.dumps(manifest, separators=(",", ":")) + "\n"
        data["files"].pop("road.xodr", None)
        folder = HERE / "cases" / suffix
        spec_path = folder / "diagnostic-spec.json"
        write(spec_path, data)
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "road.xodr", "source": "work/" + ASSIGNMENT + "/diagnostic-map.xodr",
                               "sha256": sha(map_bytes)}],
                  "generator": {"source": str(spec_path.relative_to(REPO)),
                                "sha256": sha(spec_path.read_bytes())}}
        write(folder / "diagnostic-recipe.json", recipe)
        if spec_path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("diagnostic spec exceeds returned file limit")
    print("Built 18 bounded synthetic highway/HOV diagnostic recipes")


if __name__ == "__main__":
    main()
