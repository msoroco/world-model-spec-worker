"""CPU source-replay proof for each planned comparison; diagnostic only."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from saved_pair import audit_saved_pair

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tests"))
from test_saved_turn import SavedTurnTests


def rows_for(suffix, base):
    rows = [dict(row) for row in base]
    for row in rows:
        row["pedestrian_xy"] = [1, 1] if suffix in ("yield_pedestrian", "continue_pedestrian") and row["frame"] < 2 else [5, 5]
        row["other_traffic_in_intersection"] = suffix in ("yield_other_traffic", "continue_other_traffic") and row["frame"] < 2
        row["ego_route_lane_id"] = 3 if suffix == "wrong_movement" else 2
        row["ego_in_intersection"] = row["frame"] >= (1 if suffix in ("continue_pedestrian", "continue_other_traffic") else 2)
    return rows


def run(name, negative=False):
    from comparison_audit import PAIRS
    if name not in PAIRS:
        raise ValueError("unknown planned comparison")
    fixture = SavedTurnTests()
    fixture.setUp()
    try:
        base = json.loads((fixture.root / "telemetry.json").read_text())
        profile = json.loads((fixture.root / "camera_profile.json").read_text())
        profile["duration_frames"] = 600
        profile_ref = fixture.save_json("comparison_profile", profile)
        cameras = fixture.manifest["cameras"]
        for camera, frames in cameras.items():
            raw = (fixture.root / frames[-1]["source"]["path"]).read_bytes()
            for index in range(3, 600):
                frames.append({"frame": index,
                               "source": fixture.save_bytes(camera + str(index) + ".png", raw)})
        refs = []
        for suffix in PAIRS[name]:
            rows = rows_for(suffix, base)
            for index in range(3, 600):
                rows.append(dict(rows[-1], frame=index))
            telemetry = fixture.save_json(suffix + "_telemetry", rows)
            manifest = dict(fixture.manifest, case_suffix=suffix, duration_frames=600,
                            telemetry=telemetry, camera_profile=profile_ref)
            refs.append(fixture.save_json(suffix + "_manifest", manifest))
        if negative:
            path = fixture.root / refs[1]["path"]
            path.write_bytes(path.read_bytes() + b" ")
        receipt = audit_saved_pair(name, fixture.root, refs[0], fixture.root, refs[1],
                                   expected_frames=600, diagnostic=True)
        if receipt["decoded_view_frames"] != 4800 or receipt["physical_acceptance"]:
            raise ValueError("comparison replay did not decode all original-shaped views")
        print(json.dumps(receipt, sort_keys=True))
    finally:
        fixture.tmp.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    run(args.comparison, args.negative)
