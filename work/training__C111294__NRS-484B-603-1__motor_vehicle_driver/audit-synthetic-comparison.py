"""Independent controlled-pair audit of the two synthetic intersection attempts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    summary = json.loads((HERE / "synthetic-core-integration.json").read_text())
    items = {r["case_id"].split("__")[-1]: r for r in summary["results"]}
    assert set(items) == {"probe_a", "probe_b"}
    folders = {k: Path(v["core"]["output"]).parent / "attempt" for k, v in items.items()}
    a, b = folders["probe_a"], folders["probe_b"]
    assert sha(a / "road.xodr") == sha(b / "road.xodr")
    assert sha(a / "video_frames.jsonl") == sha(b / "video_frames.jsonl")
    ca, cb = (json.loads((p / "config.json").read_text()) for p in (a, b))
    differing = {key for key in ca if ca[key] != cb[key]}
    assert differing == {"case_id", "case_suffix", "selected_case_id", "supported_case_ids", "case", "knobs"}
    common_knobs = set(ca["knobs"]) & set(cb["knobs"])
    assert all(ca["knobs"][key] == cb["knobs"][key] for key in common_knobs)
    assert ca["knobs"]["other_start_x_m"] == cb["knobs"]["other_start_x_m"]
    sa, sb = rows(a / "native_samples.jsonl"), rows(b / "native_samples.jsonl")
    assert len(sa) == len(sb) == 480
    for index, (left, right) in enumerate(zip(sa, sb)):
        assert left["frame"] == right["frame"] == index
        assert left["native_frame"] == right["native_frame"]
        assert left["time_s"] == right["time_s"]
        assert left["ego_actor_id"] == right["ego_actor_id"] == 101
        assert left["other_actor_id"] == right["other_actor_id"] == 202
        assert left["ego_role"] == right["ego_role"] == "motor_vehicle_driver"
        assert left["other_role"] == right["other_role"] == "motor_vehicle_driver"
        assert left["other_position_m"] == right["other_position_m"]
        assert left["ego_position_m"][0] == right["ego_position_m"][0]
    assert sa[0]["ego_position_m"] == sb[0]["ego_position_m"]
    assert sa[0]["ego_velocity_mps"] == sb[0]["ego_velocity_mps"]
    ra, rb = (json.loads((p / "analysis-report.json").read_text()) for p in (a, b))
    va = ra["measurements"]["intersection_approach"]["value"]
    vb = rb["measurements"]["intersection_approach"]["value"]
    assert va["measured_relation"] == "measured_early_decrease_held"
    assert vb["measured_relation"] == "measured_no_material_decrease"
    assert va["measured_decrease_mph"] >= 3.0
    assert vb["measured_decrease_mph"] < 1.0
    assert va["other_vehicle_displacement_m"] == vb["other_vehicle_displacement_m"]
    assert not va["physical_hazard_observed"] and not vb["physical_hazard_observed"]
    print(json.dumps({"passed": True, "frames_per_case": 480,
                      "fixed_map_sha256": sha(a / "road.xodr"),
                      "fixed_other_trajectory": True,
                      "measured_decrease_mph": {"probe_a": va["measured_decrease_mph"],
                                                "probe_b": vb["measured_decrease_mph"]},
                      "scope": "synthetic CPU controlled comparison; no physical or legal outcome",
                      "ready": False}, sort_keys=True))


if __name__ == "__main__":
    main()
