"""Check exact case identities and the two isolated construction contrasts."""

import json

from capture_plan import CASES, build, validate_matrix


def prove() -> dict:
    checked = validate_matrix()
    negatives = {}
    for suffix in ("missing", "witness_3"):
        try:
            build(suffix)
        except ValueError as exc:
            negatives[suffix] = str(exc)
        else:
            raise AssertionError("unknown exact case accepted")
    try:
        build("witness_1", stop_center_x_m=9.9)
    except ValueError as exc:
        negatives["target_outside_zone"] = str(exc)
    else:
        raise AssertionError("outside-zone parking target accepted")
    assert len(CASES) == len(checked["plans"]) == 4
    assert all(plan["primary_max_speed_mps"] == 4.0 and
               plan["fallback1"]["max_speed_mps"] == 3.0 and
               plan["fallback1"]["same_case_and_observations"]
               for plan in checked["plans"].values())
    assert len({plan["requested_open_drive_sha256"] for plan in
                checked["plans"].values()}) == 1
    assert all(plan["requested_zone_bounds_m"] == [0.0, -4.0, 10.0, -1.0]
               and plan["requested_sign_id"] == "510" for plan in
               checked["plans"].values())
    return {"format": "restricted-zone-capture-plan-proof-v1",
            "case_ids": [p["case_id"] for p in checked["plans"].values()],
            "comparison_count": checked["comparison_count"],
            "candidate_speed_caps_mps": [4.0, 3.0],
            "negative_rejections": negatives,
            "native_execution_started": False,
            "actual_purpose_or_exchange_observed": False}


if __name__ == "__main__":
    print(json.dumps(prove(), sort_keys=True))
