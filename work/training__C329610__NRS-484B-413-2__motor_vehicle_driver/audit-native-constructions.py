"""Independent manifest and controlled-knob audit for 24 Native requests."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest = json.loads((HERE / "native-construction-manifest.json").read_text())
    assert hashlib.sha256((HERE / "native-constructions/scene.xodr").read_bytes()).hexdigest() == manifest["map_sha256"]
    assert len(manifest["candidates"]) == 24 and not manifest["selected"] and not manifest["native_executed"]
    grouped = {}
    for entry in manifest["candidates"]:
        raw = (REPO / entry["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry["sha256"]
        c = json.loads(raw)
        assert c["case_id"] == entry["case_id"] and c["candidate_id"] == entry["candidate_id"]
        assert (c["law_id"], c["cell_id"], c["actor"]) == (plan["law_id"], plan["cell_id"], plan["actor"])
        assert c["map_sha256"] == manifest["map_sha256"] and c["source_assignment_sha256"] == plan["sources"][0]["sha256"]
        assert c["rate_hz"] == 20 and c["duration_s"] == 40 and not c["physical_success_claimed"]
        assert c["signal_direction"] == "left" and c["turn_entry_x_m"] == -7
        assert abs((-7 - c["signal_onset_x_m"]) / .3048 - c["target_signal_distance_ft"]) < 1e-8
        assert c["route_xy_m"][0][0] == c["start_x_m"] and c["start_x_m"] + 2.6 < c["signal_onset_x_m"]
        assert all(-120 < p[0] < 101 and -7 < p[1] < 51 for p in c["route_xy_m"])
        grouped.setdefault(c["case_id"], {})[c["candidate_id"]] = c
    assert len(grouped) == 6
    for case in plan["cases"]:
        group = grouped[case["case_id"]]
        assert set(group) == {"primary", "fallback1", "fallback2", "fallback3"}
        assert all(c["target_signal_distance_ft"] == case["requested_setting"] and
                   c["area"] == case["area_classification"] and c["weather"] == "clear" for c in group.values())
        p = group["primary"]
        assert group["fallback1"]["start_x_m"] < p["start_x_m"] and group["fallback1"]["target_speed_mps"] == p["target_speed_mps"]
        assert group["fallback2"]["start_x_m"] == p["start_x_m"] and group["fallback2"]["target_speed_mps"] < p["target_speed_mps"]
        assert group["fallback3"]["start_x_m"] == p["start_x_m"] and group["fallback3"]["camera_policy"] != p["camera_policy"]
        assert len({c["trigger"] for c in group.values()}) == 4
    print(json.dumps({"cases_audited": 6, "native_requests_audited": 24, "selected": False,
                      "native_executed": False}))


if __name__ == "__main__":
    main()
