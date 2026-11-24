"""CPU diagnostic proof with 600 source-shaped frames and negative controls."""

import hashlib
import json
from pathlib import Path

from curb_measurement import CAMERAS, FRAME_COUNT, SOURCE_HASHES, measure
from curb_scene_request import CASES_IN, VARIANTS, request, validate_request

HERE = Path(__file__).resolve().parent


def context(uncertainty_in=0.25):
    value = {"source_kind": "native_c229398_wheel_curb_readback",
             "highway_adjacent_curbs": True, "right_curb_confirmed": True,
             "ordinance_authority_status": "unverified_no_exception_claim",
             "right_curb_polyline_xy_m": [[-60, -4], [60, -4]],
             "wheel_curb_uncertainty_m": uncertainty_in * 0.0254}
    for name in SOURCE_HASHES:
        value[name + "_sha256"] = hashlib.sha256(("synthetic_source:" + name).encode()).hexdigest()
    return value


def trace(gap_in):
    wheel_y = -4 + gap_in * 0.0254
    result = []
    for i in range(FRAME_COUNT):
        parked = 180 <= i <= 480
        result.append({"native_frame": 300000 + i, "video_frame": i,
                       "time_s": i / 20, "source_cameras": {name: i for name in CAMERAS},
                       "ego_speed_mps": 0.0 if parked else 1.5,
                       "parking_brake_applied": parked,
                       "ego_center_xy_m": [0, wheel_y + 0.8],
                       "right_front_wheel_outer_xy_m": [1.3, wheel_y],
                       "right_rear_wheel_outer_xy_m": [-1.3, wheel_y],
                       "ego_heading_deg": 0})
    return result


def reject(name, ctx, rows, expected):
    try:
        measure(ctx, rows)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(f"{name}: unexpected {error}") from error
        return {"name": name, "error": str(error)}
    raise AssertionError(name + " unexpectedly passed")


def main():
    scenes = {}
    for case in CASES_IN:
        for variant in VARIANTS:
            scene = request(case, variant)
            assert validate_request(scene)
            assert abs(scene["controller"]["requested_gap_in"] - CASES_IN[case]) < 1e-12
            scenes[case + ":" + variant] = {
                "request_sha256": hashlib.sha256(json.dumps(scene, sort_keys=True).encode()).hexdigest(),
                "requested_gap_in": scene["controller"]["requested_gap_in"]}
    positive = {str(gap): measure(context(), trace(gap)) for gap in (16, 18, 20)}
    assert positive["16"]["boundary_bracket"] == "strictly_within_18_in_diagnostic"
    assert positive["18"]["boundary_bracket"] == "straddles_18_in_boundary"
    assert positive["20"]["boundary_bracket"] == "strictly_beyond_18_in_diagnostic"
    assert all(value["parked_frame_count"] == 301 for value in positive.values())
    negative = []
    ctx = context()
    ctx.pop("wheel_geometry_sha256")
    negative.append(reject("missing_wheel_source", ctx, trace(18), "Missing source hash"))
    ctx = context()
    ctx["ordinance_authority_status"] = "assumed_permitted"
    negative.append(reject("invented_ordinance", ctx, trace(18), "Ordinance authority"))
    negative.append(reject("short_trace", context(), trace(18)[:-1], "Incomplete"))
    rows = trace(18)
    rows[180]["source_cameras"].pop("wheel_closeup")
    negative.append(reject("camera_missing", context(), rows, "Four source camera"))
    rows = trace(18)
    rows[180]["native_frame"] = rows[179]["native_frame"]
    negative.append(reject("duplicate_native_frame", context(), rows, "Native frame"))
    rows = trace(18)
    rows[180]["right_front_wheel_outer_xy_m"][1] = -4.01
    negative.append(reject("wheel_beyond_curb", context(), rows, "beyond curb"))
    rows = trace(18)
    rows[180]["right_front_wheel_outer_xy_m"][1] = rows[180]["ego_center_xy_m"][1] + 0.2
    negative.append(reject("wheel_side", context(), rows, "side inconsistent"))
    rows = trace(18)
    for row in rows:
        row["parking_brake_applied"] = False
    negative.append(reject("no_parked_interval", context(), rows, "interval missing"))
    output = {"format": "worker-c229398-curb-cpu-proof", "passed": True,
              "diagnostic_only": True, "native_observed": False,
              "fixture_kind": "synthetic_native_sample", "scenes": scenes,
              "positive": positive, "negative": negative}
    path = HERE / "curb-cpu-proof.json"
    path.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
