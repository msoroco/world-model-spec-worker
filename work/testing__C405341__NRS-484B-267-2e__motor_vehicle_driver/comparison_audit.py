"""Independent ten-comparison audit over original emergency lane deliveries."""
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
    require(len(matches) == 1, "unknown exact emergency lane comparison")
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
                and item.get("scene_context", {}).get("lane_graph_sha256")
                and item.get("lane_pixel_audit", {}).get("ego_lane_original_frames"),
                "source-bound original emergency lane case audit required")
        audits.append(item)
        sources[case_id] = hashlib.sha256(path.read_bytes()).hexdigest()
    varying = {
        "available_lane_choice": {"ego_route_sha256"},
        "traffic_exception": {"traffic_sha256"},
        "roadway_exception": {"road_source_sha256", "lane_graph_sha256", "ego_route_sha256"},
        "weather_exception": {"weather_sha256"},
        "other_hazard_exception": set(),
        "officer_exception": set(),
        "preparing_cue_alternatives": {"unit_route_sha256"},
        "target_class_alternative": set(),
        "flashing_activation": set(),
        "approach_activation": {"ego_route_sha256"},
    }
    require(comparison_id in varying, "unknown exact emergency lane comparison")
    keys = ("road_source_sha256", "weather_sha256", "traffic_sha256",
            "ego_route_sha256", "camera_plan_sha256", "unit_route_sha256", "lane_graph_sha256")
    for key in keys:
        if key not in varying[comparison_id]:
            require(len({item["scene_context"][key] for item in audits}) == 1,
                    "fixed original condition changed: " + key)
    if comparison_id != "target_class_alternative":
        require(len({item["authority"]["class"] for item in audits}) == 1 and
                len({item["authority"]["equipment_source"] for item in audits}) == 1,
                "fixed unit authority or equipment changed")
    counts = [item["original_condition_counts"] for item in audits]
    lane_histories = [item["lane_pixel_audit"]["ego_lane_original_frames"] for item in audits]
    if comparison_id == "available_lane_choice":
        require(lane_histories[0] != lane_histories[1] and
                audits[0]["lane_site"]["nonadjacent_route_connected"] is True and
                audits[1]["lane_site"]["nonadjacent_route_connected"] is True,
                "original available-lane choice difference missing")
        proof = {"ego_lane_histories_differ": True}
    elif comparison_id == "traffic_exception":
        require(counts[0]["traffic_occupied_frames"] == 0 and counts[1]["traffic_occupied_frames"] > 0,
                "original traffic path occupation difference missing")
        proof = {"traffic_occupied_frames": [v["traffic_occupied_frames"] for v in counts]}
    elif comparison_id == "roadway_exception":
        availability = [item["lane_site"]["nonadjacent_route_connected"] for item in audits]
        require(availability == [True, False], "original nonadjacent route availability difference missing")
        proof = {"nonadjacent_route_connected": availability}
    elif comparison_id == "weather_exception":
        require(counts[0]["weather_adverse_frames"] == 0 and counts[1]["weather_adverse_frames"] > 0,
                "original weather condition difference missing")
        proof = {"weather_adverse_frames": [v["weather_adverse_frames"] for v in counts]}
    elif comparison_id == "other_hazard_exception":
        require(counts[0]["other_hazard_frames"] == 0 and counts[1]["other_hazard_frames"] > 0,
                "original other-hazard path occupation difference missing")
        proof = {"other_hazard_frames": [v["other_hazard_frames"] for v in counts]}
    elif comparison_id == "officer_exception":
        require(counts[0]["officer_direction_frames"] == 0 and counts[1]["officer_direction_frames"] > 0,
                "source-bound law-enforcement officer direction difference missing")
        proof = {"officer_direction_frames": [v["officer_direction_frames"] for v in counts]}
    elif comparison_id == "preparing_cue_alternatives":
        movement = [item["lane_pixel_audit"]["movement_visible_frames"] for item in audits]
        hand = [item["lane_pixel_audit"]["hand_signal_visible_frames"] for item in audits]
        require(len(audits) == 3 and movement[1] > 0 and hand[2] > 0,
                "original movement and hand-signal preparation alternatives missing")
        proof = {"movement_visible_frames": movement, "hand_signal_visible_frames": hand}
    elif comparison_id == "target_class_alternative":
        classes = [item["authority"]["class"] for item in audits]
        require(classes == ["authorized_emergency", "regulatory_official"],
                "original emergency/regulatory class alternatives missing")
        proof = {"unit_classes": classes}
    elif comparison_id == "flashing_activation":
        flashes = [v["flashing_frames"] for v in counts]
        require(flashes[0] > 0 and flashes[1] == 0,
                "original qualifying flashing-light use difference missing")
        proof = {"flashing_frames": flashes}
    else:
        approaches = [v["approaching_frames"] for v in counts]
        require(approaches[0] > 0 and approaches[1] == 0,
                "original ego approach difference missing")
        proof = {"approaching_frames": approaches}
    return {"format": "c405341-2e-original-comparison-audit-v1",
        "assignment_id": AID, "comparison_id": comparison_id,
        "case_ids": expected, "case_audit_sha256": sources,
        "comparison_proof": proof,
        "fixed_camera_plan_sha256": audits[0]["scene_context"]["camera_plan_sha256"],
        "legal_possible_and_safe": "unresolved", "legal_status": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--audit", action="append", nargs=2,
                        metavar=("CASE_ID", "PATH"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior emergency lane comparison audit")
    pairs = dict(args.audit)
    require(len(pairs) == len(args.audit), "duplicate case audit")
    args.output.write_text(json.dumps(audit_comparison(args.comparison, pairs),
                                      indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
