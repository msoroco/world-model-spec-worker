"""Independent readback of authored fallback quality measurements."""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def audit():
    proof = json.loads((HERE / "fallback-quality-proof.json").read_text())
    if proof.get("synthetic_preflight_only") is not True or proof.get("delivery_ready") is not False:
        raise ValueError("Fallback proof provenance changed")
    checked = 0
    for record in proof["records"]:
        suffix = record["case_id"]
        measured = record["measured_requests"]
        for candidate, saved in measured.items():
            bundle = HERE / "drafts" / suffix / candidate
            rows = [json.loads(line) for line in (bundle / "requested-tracks.jsonl").read_text().splitlines()]
            approach = [r for r in rows if r["requested_phase"] == "approach"]
            hold = [r for r in rows if r["requested_phase"] == "yield_hold"]
            movement = [r for r in rows if r["requested_phase"] == "intersection_movement"]
            speed = round(max(math.dist(a["requested_ego_xyz_m"], b["requested_ego_xyz_m"]) * 20
                              for a, b in zip(approach, approach[1:])), 4)
            window = round((movement[0]["frame"] - hold[0]["frame"]) / 20, 4)
            cfg = json.loads((bundle / "config.json").read_text())
            if (len(rows) != 480 or saved["approach_speed_mps"] != speed or
                    saved["yield_hold_to_entry_window_s"] != window or
                    saved["camera_policy"] != cfg["camera_policy"] or
                    saved["original_native_observed"] is not False):
                raise ValueError("Fallback measurement differs from request rows")
            checked += 1
        if not (measured["primary"]["approach_speed_mps"] > 7 > measured["fallback1"]["approach_speed_mps"]):
            raise ValueError("Slower approach contrast missing")
        if measured["fallback2"]["camera_policy"] != "elevated_overview":
            raise ValueError("Overview contrast missing")
        if measured["fallback3"]["yield_hold_to_entry_window_s"] <= measured["primary"]["yield_hold_to_entry_window_s"]:
            raise ValueError("Longer signal window contrast missing")
    result = {"format": "c111603-3079a-fallback-quality-audit-v1",
              "measured_candidates": checked, "controlled_cases": len(proof["records"]),
              "original_native_observed": False, "delivery_ready": False}
    (HERE / "fallback-quality-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps(audit(), sort_keys=True))
