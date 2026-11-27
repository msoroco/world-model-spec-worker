"""Synthetic CPU geometry and source-join proof; not physical evidence."""

import hashlib
import json
from pathlib import Path

from measure_tunnel import measure
from one_way_variant import HIGHWAY_CENTRE_Y_M, TARGETS, request, validate
from prove_tunnel import context, trace


def rows_for(case):
    rows = trace(left=False)
    target = TARGETS[case]
    for row in rows:
        old_y = sum(point[1] for point in row["body_xy_m"]) / 4
        for point in row["body_xy_m"]:
            point[1] += target - old_y
    return rows


def reject(label, value, expected):
    try:
        validate(value)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError((label, str(error))) from error
        return {"test": label, "rejected": str(error)}
    raise AssertionError(label + " unexpectedly passed")


def main():
    checks = []
    for case in TARGETS:
        authored = request(case)
        validation = validate(authored)
        source = context(one_way=True)
        source["highway_centre_y_m"] = HIGHWAY_CENTRE_Y_M
        measured = measure(source, rows_for(case))
        if measured["one_way_highway_surveyed"] is not True:
            raise AssertionError("One-way source context lost")
        checks.append({"case": case, "authoring": validation,
                       "diagnostic_within_zone_frames": measured["within_100_ft_driving_frames"],
                       "diagnostic_left_within_zone_frames": measured["left_of_centre_within_zone_frames"],
                       "diagnostic_legal_compliance": measured["legal_compliance"]})
    if checks[0]["diagnostic_left_within_zone_frames"] != 0 or checks[1]["diagnostic_left_within_zone_frames"] == 0:
        raise AssertionError("Controlled one-way lateral contrast missing")
    negatives = []
    value = request("one_way_left")
    value["original_direction_readback"]["required_lane_ids"] = [-1]
    negatives.append(reject("missing second lane survey", value, "direction proof"))
    value = request("one_way_left")
    value["road_opendrive"] = value["road_opendrive"].replace('id="-2"', 'id="2"')
    negatives.append(reject("opposing lane", value, "lane geometry"))
    value = request("one_way_left")
    value["highway_centre_y_m"] = 0.0
    negatives.append(reject("changed center", value, "lateral target"))
    value = request("one_way_left")
    value["cameras"] = value["cameras"][:-1]
    negatives.append(reject("missing camera", value, "camera, duration"))
    source = context(one_way=True)
    source["highway_centre_y_m"] = HIGHWAY_CENTRE_Y_M
    source["one_way_native_survey"] = None
    try:
        measure(source, rows_for("one_way_left"))
    except ValueError as error:
        if "One-way" not in str(error):
            raise
        negatives.append({"test": "missing one-way source", "rejected": str(error)})
    else:
        raise AssertionError("Missing original one-way survey unexpectedly passed")
    proof = {"format": "worker-one-way-tunnel-cpu-diagnostic-proof",
             "passed": True, "diagnostic_only": True,
             "original_native_observed": False,
             "positive": checks, "negative": negatives,
             "unverified": ["Original Native one-way map readback",
                            "Original four-camera pixels and tunnel/view geometry",
                            "Actual body trajectory and legal outcome"]}
    path = Path(__file__).with_name("one-way-variant-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "positive_count": len(checks),
                      "negative_count": len(negatives),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
