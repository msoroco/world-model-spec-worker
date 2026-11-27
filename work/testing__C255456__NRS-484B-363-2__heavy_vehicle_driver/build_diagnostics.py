"""Materialize case-specific textual CPU fixtures, never original evidence."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / "case-plan.json").read_text())
OLD = "testing__C262661__NRS-484B-363-1__bus_driver"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, separators=(",", ":"), ensure_ascii=False) + "\n")


def build(case):
    suffix = case["case_id"].split("__")[-1]
    folder = ROOT / "cases" / suffix
    folder.mkdir(parents=True, exist_ok=True)
    scaffold = (ROOT / "diagnostic-template.json").read_text()
    scaffold = scaffold.replace(OLD + "__beacon_flashing_14_9", case["case_id"])
    scaffold = scaffold.replace(OLD, PLAN["assignment_id"])
    scaffold = scaffold.replace("14.9", str(case["speed_target_mph"]))
    scaffold = scaffold.replace("vehicle.school_bus", "vehicle.heavy_truck")
    scaffold_path = folder / "diagnostic-scaffold.json"
    scaffold_path.write_text(scaffold.rstrip() + "\n")
    source_folder = folder / "diagnostic-sources"
    source_folder.mkdir(exist_ok=True)
    context = {"case_id": case["case_id"],
               "school_in_session_today": case["session_request"] == "session",
               "time_window_label": case["time_request"],
               "beacon_or_sign_state": case["beacon_or_sign_request"],
               "diagnostic_fixture": True,
               "source_limit": "Textual software fixture, not a reviewed school site"}
    write(source_folder / "context.json", context)
    device = case["beacon_or_sign_request"]
    rows = []
    for index in range(9):
        lamps = ([index % 2 == 0, index % 2 == 1]
                 if device == "operational_flashing" else
                 [False, False] if device == "operational_not_flashing" else
                 [index % 2 == 0] if device == "one_yellow_light" else
                 [True, False] if device == "nonalternating_yellow" else [])
        rows.append({"frame": index, "time_s": index / 20,
                     "heavy_speed_mps": case["speed_target_mph"] / 2.2369362921,
                     "inside_designated_zone": case["zone_request"] == "inside",
                     "sign_limit_active": device != "nonbeacon_sign_off",
                     "beacon_yellow_lights_lit": lamps,
                     "children_actor_ids": ["diagnostic_child"] if
                         case["children_request"] == "children" else []})
    (source_folder / "original-trace.jsonl").write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))
    write(source_folder / "cameras.json", {
        "case_id": case["case_id"], "fps": 20, "frame_count": 9,
        "views": ["overview", "approach", "reference_corner", "driver_reference"],
        "diagnostic_fixture": True})
    write(source_folder / "receipt.json", {
        "source_kind": "synthetic_diagnostic_fixture", "diagnostic_fixture": True,
        "assignment_id": PLAN["assignment_id"], "case_id": case["case_id"],
        "context_sha256": sha(source_folder / "context.json"),
        "trace_sha256": sha(source_folder / "original-trace.jsonl"),
        "camera_manifest_sha256": sha(source_folder / "cameras.json")})
    inputs = ("context.json", "original-trace.jsonl", "receipt.json", "cameras.json")
    requirements = []
    for index, row in enumerate(PLAN["requirement_dispositions"]):
        if case["case_id"] in row["case_ids"]:
            requirements.append({"disposition_index": index, "inputs": list(inputs),
                                 "kind": "measured", "method": "analyze",
                                 "output_key": f"school_heavy_requirement_{index}",
                                 "requirement": row["requirement"],
                                 "source": row["source"], "value_type": "object"})
    write(folder / "measurement-contract.json", {
        "case_id": case["case_id"], "format": "worker-measurement-contract",
        "negative": {"remove": ["context.json"],
                     "error_contains": "Missing required source: context.json"},
        "requirements": requirements})
    write(folder / "fixture-recipe.json", {
        "format": "worker-fixture-recipe",
        "sources": [{"path": name,
                     "source": str((source_folder / name).relative_to(ROOT.parents[1])),
                     "sha256": sha(source_folder / name)} for name in inputs],
        "generator": {"source": str(scaffold_path.relative_to(ROOT.parents[1])),
                      "sha256": sha(scaffold_path)}})
    return suffix


def main():
    for case in PLAN["cases"]:
        print(build(case))


if __name__ == "__main__":
    main()
