"""Exercise the independent delivery source audit on labeled CPU diagnostics."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from comparison_probe import rows_for
from delivery_audit import audit

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tests"))
from test_saved_turn import SavedTurnTests


def run(case_id, negative=False):
    suffix = case_id.rsplit("__", 1)[-1]
    if suffix not in ("yield_pedestrian", "continue_pedestrian", "clear_crosswalk_turn",
                      "wrong_movement", "yield_other_traffic", "continue_other_traffic"):
        raise ValueError("unknown selected red-plus-arrow case")
    fixture = SavedTurnTests()
    fixture.setUp()
    try:
        base = json.loads((fixture.root / "telemetry.json").read_text())
        rows = rows_for(suffix, base)
        for index in range(3, 600):
            rows.append(dict(rows[-1], frame=index))
        site = json.loads((fixture.root / "site.json").read_text())
        site["source_kind"] = "cpu_diagnostic_only"
        site["case_id"] = case_id
        fixture.manifest["site"] = fixture.save_json("diagnostic_site", site)
        fixture.manifest["case_suffix"] = suffix
        fixture.manifest["duration_frames"] = 600
        fixture.manifest["telemetry"] = fixture.save_json("diagnostic_telemetry", rows)
        profile = json.loads((fixture.root / "camera_profile.json").read_text())
        profile["duration_frames"] = 600
        fixture.manifest["camera_profile"] = fixture.save_json("diagnostic_profile", profile)
        for camera, frames in fixture.manifest["cameras"].items():
            raw = (fixture.root / frames[-1]["source"]["path"]).read_bytes()
            for index in range(3, 600):
                frames.append({"frame": index,
                               "source": fixture.save_bytes(camera + str(index) + ".png", raw)})
        (fixture.root / "config.json").write_text(json.dumps({"selected_case_id": case_id}) + "\n")
        fixture.save_json("manifest", fixture.manifest)
        if negative:
            path = fixture.root / fixture.manifest["cameras"]["driver_reference"][0]["source"]["path"]
            path.write_bytes(path.read_bytes() + b" ")
        result = audit(fixture.root, case_id, diagnostic=True)
        if result["decoded_original_png_frames"] != 2400 or result["physical_acceptance_claimed"]:
            raise ValueError("diagnostic replay did not inspect every original-shaped PNG")
        print(json.dumps(result, sort_keys=True))
    finally:
        fixture.tmp.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    run(args.case, args.negative)
