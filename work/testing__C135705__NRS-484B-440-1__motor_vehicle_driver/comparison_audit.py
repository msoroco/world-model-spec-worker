"""Independent exact-pair audit for C135705 contrast consistency."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit as audit_delivery

PAIRS={"passage_width_with_fixed_view":("passage_clear_view","passage_blocked"),
       "two_sided_visibility_with_fixed_passage":("passage_clear_view","view_occluded_both")}


def audit(comparison_id,left,right,*,diagnostic_test=False):
    if comparison_id not in PAIRS:raise ValueError("unknown comparison")
    a,b=[Path(x).resolve() for x in (left,right)]
    receipts=[audit_delivery(path,diagnostic_test=diagnostic_test) for path in (a,b)]
    if [r["case_id"].rsplit("__",1)[1] for r in receipts]!=list(PAIRS[comparison_id]):
        raise ValueError("exact case pair/order differs")
    scenes=[json.loads((path/"scene.json").read_text()) for path in (a,b)]
    measurements=[json.loads((path/"standing-measurement.json").read_text())["measured"] for path in (a,b)]
    fixed=("map_source_sha256","paved_road_xy_m","shoulder_negative_y_xy_m",
           "shoulder_positive_y_xy_m","other_vehicle_centers_xy_m",
           "other_vehicle_half_length_m","other_vehicle_half_width_m",
           "sight_eye_y_m","sight_probe_distances_m","standing_blueprint_id",
           "passing_blueprint_id","disabled_physical_mechanism")
    if any(scenes[0][key]!=scenes[1][key] for key in fixed):
        raise ValueError("declared fixed construction condition changed")
    if comparison_id=="passage_width_with_fixed_view":
        if scenes[0]["sight_occluders_xy_m"]!=scenes[1]["sight_occluders_xy_m"]:
            raise ValueError("sight occluders changed in width comparison")
        if not (measurements[0]["minimum_unobstructed_opposite_width_m"]>
                measurements[1]["minimum_unobstructed_opposite_width_m"]):
            raise ValueError("measured opposite width contrast absent")
        if not measurements[0]["physical_passage_observed"] or measurements[1]["physical_passage_observed"]:
            raise ValueError("measured passage contrast absent")
    else:
        if scenes[0]["standing_body_xy_m"]!=scenes[1]["standing_body_xy_m"]:
            raise ValueError("standing body changed in visibility comparison")
        if not all(m["physical_passage_observed"] for m in measurements):
            raise ValueError("passage not fixed in sight comparison")
        if not scenes[1]["sight_occluders_xy_m"] or scenes[0]["sight_occluders_xy_m"]:
            raise ValueError("sight occluder construction contrast absent")
    return {"format":"worker-comparison-audit","comparison_id":comparison_id,
            "case_ids":[r["case_id"] for r in receipts],"status":"cpu_source_audit_passed",
            "fixed_conditions_checked":list(fixed),"physical_acceptance_claimed":False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument("comparison_id");parser.add_argument("left");parser.add_argument("right")
    parser.add_argument("--diagnostic-test",action="store_true")
    args=parser.parse_args();print(json.dumps(audit(args.comparison_id,args.left,args.right,
                                                diagnostic_test=args.diagnostic_test),indent=2))


if __name__=="__main__":main()
