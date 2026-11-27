"""Independent four-comparison audit over original emergency delivery audits."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_packet import AID

HERE = Path(__file__).resolve().parent


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit_comparison(comparison_id, audit_paths):
    plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
    matches = [row for row in plan["comparisons"] if row["comparison_id"] == comparison_id]
    require(len(matches) == 1, "unknown exact emergency comparison")
    expected = matches[0]["case_ids"]
    require(set(audit_paths) == set(expected) and len(audit_paths) == len(expected),
            "comparison must include every exact case once")
    audits, sources = [], {}
    for case_id in expected:
        path = Path(audit_paths[case_id])
        require(path.is_file() and not path.is_symlink(), "original case audit missing")
        item = json.loads(path.read_text(encoding="utf-8"))
        require(item.get("format") == "c405341-2e-original-delivery-audit-v1"
                and item.get("case_id") == case_id
                and item.get("original_frame_count") == 900
                and item.get("legal_status") == "unresolved"
                and item.get("source_sha256", {}).get("capture-seal.json")
                and item.get("scene_context", {}).get("road_source_sha256"),
                "source-bound original emergency case audit required")
        audits.append(item)
        sources[case_id] = hashlib.sha256(path.read_bytes()).hexdigest()
    for key in ("road_source_sha256", "weather_sha256", "ego_route_sha256", "camera_plan_sha256"):
        require(len({item["scene_context"][key] for item in audits}) == 1,
                "fixed original road, weather, ego route or camera changed: " + key)
    if comparison_id != "vehicle_and_cue_alternatives":
        require(len({item["scene_context"]["unit_route_sha256"] for item in audits}) == 1
                and len({item["authority"]["class"] for item in audits}) == 1
                and len({item["authority"]["equipment_source"] for item in audits}) == 1,
                "fixed emergency unit, route or equipment changed")
    first = audits[0]
    if comparison_id == "movement_visibility":
        require(len(audits) == 2, "visibility pair required")
        require(first["authority"]["class"] == audits[1]["authority"]["class"] and
                first["authority"]["equipment_source"] == audits[1]["authority"]["equipment_source"] and
                first["scene_context"]["unit_route_sha256"] == audits[1]["scene_context"]["unit_route_sha256"],
                "visibility pair changed emergency unit or route")
        values = [item["cue_pixel_audit"]["movement_visible_frames"] for item in audits]
        require(values[0] > 0 and values[1] == 0, "original movement visibility difference missing")
        proof = {"movement_visible_frames": values}
    elif comparison_id == "driver_response":
        require(len(audits) == 2 and all(item["cue_pixel_audit"]["movement_visible_frames"] > 0
                                          for item in audits), "visible movement fixed condition missing")
        values = [item["measurement"].get("brake_observations_after_cue") for item in audits]
        require(all(isinstance(value, list) and value for value in values),
                "original ego response history missing")
        maxima = [max(pair[1] for pair in value) for value in values]
        require(maxima[0] > maxima[1], "original ego braking difference missing")
        proof = {"maximum_brake_after_cue": maxima}
    elif comparison_id == "officer_direction_exception":
        require(len(audits) == 2 and all(item["cue_pixel_audit"]["movement_visible_frames"] > 0
                                          for item in audits), "visible movement fixed condition missing")
        directions = [item["measurement"].get("officer_directions", []) for item in audits]
        require(not directions[0] and directions[1], "source-bound officer direction difference missing")
        proof = {"officer_direction_frames": [len(value) for value in directions]}
    elif comparison_id == "vehicle_and_cue_alternatives":
        require(len(audits) == 3, "emergency/regulatory/hand-signal trio required")
        classes = [item["authority"]["class"] for item in audits]
        require(classes == ["authorized_emergency", "regulatory_official", "authorized_emergency"],
                "original emergency/regulatory class alternatives missing")
        require(audits[0]["cue_pixel_audit"]["movement_visible_frames"] > 0 and
                audits[1]["cue_pixel_audit"]["movement_visible_frames"] > 0 and
                audits[2]["cue_pixel_audit"]["hand_signal_visible_frames"] > 0,
                "original movement/hand cue alternatives missing")
        proof = {"unit_classes": classes, "hand_signal_visible_frames":
                 audits[2]["cue_pixel_audit"]["hand_signal_visible_frames"]}
    else:
        raise ValueError("unknown exact emergency comparison")
    return {"format": "c405341-2e-original-comparison-audit-v1",
        "assignment_id": AID, "comparison_id": comparison_id,
        "case_ids": expected, "case_audit_sha256": sources,
        "comparison_proof": proof,
        "fixed_road_source_sha256": first["scene_context"]["road_source_sha256"],
        "prepared_to_stop": "unresolved", "legal_status": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--audit", action="append", nargs=2,
                        metavar=("CASE_ID", "PATH"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior emergency comparison audit")
    pairs = dict(args.audit)
    require(len(pairs) == len(args.audit), "duplicate case audit")
    args.output.write_text(json.dumps(audit_comparison(args.comparison, pairs),
                                      indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
