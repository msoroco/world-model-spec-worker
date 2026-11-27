"""Exercise each fixed-condition comparison against saved diagnostic sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from comparison_audit import audit

HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[1] / ".runtime-work/c213645-owner"
PLAN = json.loads((HERE / "case-plan.json").read_text())
BY_ID = {row["case_id"]: row for row in PLAN["cases"]}


def source_root(case_id):
    name = case_id.split("__")[-1]
    return SCRATCH / ("saved-" + name + "-output/v0001/analysis/original-attempt")


for row in PLAN["comparisons"]:
    left_id, right_id = row["case_ids"]
    receipt = audit(source_root(left_id), source_root(right_id),
                    BY_ID[left_id], BY_ID[right_id], row, diagnostic=True)
    measured = receipt["deliberate_difference_measurement"]
    if measured == "stop_halt_frame":
        different = (receipt["left"]["last_pre_sidewalk_halt_frame"] !=
                     receipt["right"]["last_pre_sidewalk_halt_frame"])
    elif measured == "pedestrian_separation_m":
        different = (receipt["left"]["minimum_pedestrian_center_separation_m"] !=
                     receipt["right"]["minimum_pedestrian_center_separation_m"])
    else:
        different = (receipt["left"]["minimum_roadway_vehicle_center_separation_m"] !=
                     receipt["right"]["minimum_roadway_vehicle_center_separation_m"])
    if not different:
        raise ValueError("Deliberate comparison difference was not measured: " + row["comparison_id"])
    name = row["comparison_id"]
    output = HERE / ("cpu-comparison-" + name + ".json")
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    (HERE / ("cpu-comparison-" + name + ".log")).write_text(
        "fixed conditions and source measurements passed; receipt sha256 " + digest + "\n")
    print(name, "comparison passed", flush=True)
