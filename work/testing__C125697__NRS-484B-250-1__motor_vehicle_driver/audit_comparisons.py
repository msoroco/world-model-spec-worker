"""Independent, source-bound CPU audit of the three NRS 484B.250(1) pairs."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED = {"entry_order", "signal_operation", "opposite_left_turn"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_case(entry, root):
    case_id = entry["case_id"]
    construction = root / entry["construction"]
    require(construction.is_file() and sha(construction) == entry["construction_sha256"],
            "Construction changed: " + case_id)
    bundle = json.loads(construction.read_text())
    config = json.loads(next(item["content"] for item in bundle["files"]
                             if item["path"] == "config.json"))
    require(config["selected_case_id"] == case_id, "Wrong case config: " + case_id)
    info = entry["compatibility_diagnostic"]
    receipt_path = root / info["receipt"]
    require(receipt_path.is_file() and sha(receipt_path) == info["sha256"],
            "Compatibility receipt changed: " + case_id)
    receipt = json.loads(receipt_path.read_text())
    require(receipt.get("passed") is True and receipt.get("case_id") == case_id and
            receipt.get("candidate_id") == "primary" and
            receipt.get("construction_sha256") == entry["construction_sha256"] and
            "negative_case_source" in receipt.get("checks", []) and
            receipt.get("negative_removed") == "crossing_history.jsonl",
            "Positive/negative source proof missing: " + case_id)
    measured = receipt.get("measurement_examples", {})
    require(all(key in measured for key in
                ("crossing_identity", "entry_order", "device_context", "opposite_turn_context")),
            "Selected measurements missing: " + case_id)
    saved_info = entry["saved_processing_diagnostic"]
    saved_path = root / saved_info["receipt"]
    require(saved_path.is_file() and sha(saved_path) == saved_info["sha256"],
            "Saved-processing receipt changed: " + case_id)
    saved = json.loads(saved_path.read_text())
    require(saved.get("passed") is True and saved.get("recorded_only") is True and
            saved.get("originals_preserved") is True and saved.get("case_id") == case_id and
            saved.get("candidate_id") == "primary" and
            saved.get("native_revision", {}).get("construction_sha256") == entry["construction_sha256"],
            "Saved source processing missing: " + case_id)
    return {"config": config, "measured": measured, "receipt": receipt,
            "construction_sha256": entry["construction_sha256"],
            "compatibility_sha256": info["sha256"], "saved_sha256": saved_info["sha256"]}


def audit_pair(comparison_id, left, right):
    a, b = left["config"], right["config"]
    av, bv = left["measured"], right["measured"]
    ac, bc = av["crossing_identity"]["value"], bv["crossing_identity"]["value"]
    require(ac["intersection_id"] == bc["intersection_id"] and
            ac["native_map_id"] == bc["native_map_id"] and
            a["actor"] == b["actor"] and a["rate_hz"] == b["rate_hz"] == 20 and
            a["duration_s"] == b["duration_s"] == 45 and
            a["site"]["crossing_polygon_xy_m"] == b["site"]["crossing_polygon_xy_m"],
            comparison_id + ": fixed crossing, actor or capture contract changed")
    ae, be = av["entry_order"]["value"], bv["entry_order"]["value"]
    ad, bd = av["device_context"]["value"], bv["device_context"]["value"]
    require(ad["native_signal_id"] == bd["native_signal_id"],
            comparison_id + ": governing signal identity changed")
    if comparison_id == "entry_order":
        require(a["site"]["routes"] == b["site"]["routes"] and
                a["site"]["entrance_road_lanes"] == b["site"]["entrance_road_lanes"] and
                a["site"]["cameras"] == b["site"]["cameras"] and
                ae["other_before_ego"] is True and be["other_before_ego"] is False and
                ad["observed_signal_states"] == bd["observed_signal_states"] == ["Off"] * 3,
                "Entry-order variable or fixed sources not demonstrated")
    elif comparison_id == "signal_operation":
        require(a["site"]["routes"] == b["site"]["routes"] and
                a["site"]["entrance_road_lanes"] == b["site"]["entrance_road_lanes"] and
                a["site"]["cameras"] == b["site"]["cameras"] and
                ae == be and ad["observed_signal_states"] == ["Off"] * 3 and
                bd["observed_signal_states"] == ["Green"] * 3 and
                av["entry_order"]["sources"]["video_frames.jsonl"] ==
                bv["entry_order"]["sources"]["video_frames.jsonl"],
                "Signal-operation variable or fixed trajectories not demonstrated")
    elif comparison_id == "opposite_left_turn":
        turn = bv["opposite_turn_context"]["value"]["opposite_left_turn_observations"]
        require(ac["highway_ids"][0] != ac["highway_ids"][1] and
                bc["highway_ids"][0] == bc["highway_ids"][1] and
                a["site"]["cameras"] == b["site"]["cameras"] and
                ae == be and ad["observed_signal_states"] == bd["observed_signal_states"] == ["Off"] * 3 and
                b["other_approach_side"] == "opposite" and
                isinstance(turn, dict) and turn.get("left_turn_intent_in_original_rows") is True and
                turn.get("statutory_exception_judgment") == "unresolved" and
                turn.get("original_body_motion", {}).get("other", {}).get("projection_on_approach_direction_m", 0) > 0 and
                len(turn.get("other_heading_samples_deg", [])) >= 3,
                "Opposed approach and source-observed left turn not demonstrated")
    else:
        raise ValueError("Unknown comparison: " + comparison_id)
    return {"comparison_id": comparison_id, "passed": True, "legal_judgment": "unresolved"}


def audit(root=HERE, plan=None, manifest=None):
    root = Path(root)
    plan = plan or json.loads((root / "case-plan.json").read_text())
    manifest = manifest or json.loads((root / "execution-manifest.json").read_text())
    comparisons = plan.get("comparisons", [])
    require(len(comparisons) == 3 and
            {item.get("comparison_id") for item in comparisons} == EXPECTED,
            "Three declared comparisons required")
    entries = {item["case_id"]: item for item in manifest["cases"]}
    require(len(entries) == 5, "Five selected cases required")
    cases = {case_id: load_case(entry, root) for case_id, entry in entries.items()}
    results = []
    for item in comparisons:
        ids = item["case_ids"]
        require(len(ids) == 2 and ids[0] != ids[1] and all(i in cases for i in ids) and
                item.get("fixed_conditions") and item.get("deliberate_differences"),
                "Incomplete comparison declaration")
        results.append(audit_pair(item["comparison_id"], cases[ids[0]], cases[ids[1]]))
    return {"format": "worker-c125697-sub1-comparison-audit", "passed": True,
            "cases": {key: {k: value[k] for k in
                            ("construction_sha256", "compatibility_sha256", "saved_sha256")}
                      for key, value in cases.items()},
            "comparisons": results,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
