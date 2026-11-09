"""Independent C101303 saved-source and comparison checks; never issues a verdict."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit_sources(attempt, case_id, expected_frames=900):
    root = Path(attempt)
    config, context = read(root / "config.json"), read(root / "surface_context.json")
    if config["selected_case_id"] != case_id:
        raise ValueError("Audit case identity differs")
    mapping, samples = rows(root / "video_frames.jsonl"), rows(root / "following_samples.jsonl")
    if len(mapping) != expected_frames or len(samples) != expected_frames:
        raise ValueError("Incomplete original frame count")
    first_lanes = (samples[0]["ego_lane_id"], samples[0]["lead_lane_id"])
    if first_lanes[0] != first_lanes[1] or first_lanes[0] != context["initial_lane_id"]:
        raise ValueError("Initial Native following lane mismatch")
    for i, (frame, sample) in enumerate(zip(mapping, samples)):
        if (frame["video_frame"] != i or sample["frame"] != frame["carla_frame"] or
                abs(sample["time_s"] - frame["time_s"]) > 1e-6):
            raise ValueError("Original frame/time join differs")
        if len(sample["ego_body_vertices_m"]) < 4 or len(sample["lead_body_vertices_m"]) < 4:
            raise ValueError("Missing participant body history")
    before = [s for s in samples if not s["lane_change_requested"]]
    if not before or any(s["ego_lane_id"] != s["lead_lane_id"] for s in before):
        raise ValueError("Pre-change moving lead relation incomplete")
    if not all(s["lead_speed_mps"] > 0 for s in before[20:]):
        raise ValueError("Lead vehicle did not move through following interval")
    result = read(root / "result.json")
    if result.get("case_id") != case_id or result.get("provenance_kind") != "native":
        raise ValueError("Sealed Native result identity/provenance differs")
    if not result.get("setup_confirmed") or not result.get("maneuver_completed"):
        raise ValueError("Native physical setup or lane transition not completed")
    feature = read(root / "pixel-evidence.json").get("scene_feature", {})
    if (feature.get("method") != "original_frame_review" or feature.get("visible") is not True or
            not feature.get("reviewer") or not feature.get("description") or
            type(feature.get("video_frame")) is not int or
            not 0 <= feature["video_frame"] < expected_frames or
            len(feature.get("bounding_box", [])) != 4):
        raise ValueError("Missing reviewed original-pixel scene feature")
    return {"case_id": case_id, "frames": expected_frames,
            "sources": {name: sha(root / name) for name in
                        ("config.json", "surface_context.json", "video_frames.jsonl",
                         "following_samples.jsonl", "result.json", "pixel-evidence.json")},
            "scene_feature": feature, "physical_completion": True,
            "legal_judgment": "unresolved"}


def compare(left, right):
    a, b = (read(Path(path) / "config.json") for path in (left, right))
    fixed = ("cell_id", "law_id", "actor", "rate_hz", "duration_s", "cameras",
             "required_atoms", "source_packets", "controller", "recording_description")
    differing = [key for key in fixed if a[key] != b[key]]
    if differing:
        raise ValueError("Comparison fixed condition differs: " + ", ".join(differing))
    if {a["initial_gap_m"], b["initial_gap_m"]} != {16.0, 26.0}:
        raise ValueError("Comparison variable does not match two exact constructions")
    context_a, context_b = (read(Path(path) / "surface_context.json") for path in (left, right))
    for key in ("map", "road_id", "crest_location_m", "initial_lane_id", "target_lane_id"):
        if context_a[key] != context_b[key]:
            raise ValueError("Comparison Native road context differs: " + key)
    return {"comparison_id": "crest_follow_gap", "fixed_checked": list(fixed),
            "Native_road_context_checked": True, "deliberate_gap_m": [a["initial_gap_m"], b["initial_gap_m"]],
            "legal_judgment": "unresolved"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--attempt")
    p.add_argument("--case")
    p.add_argument("--compare", nargs=2)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    if args.compare:
        value = compare(*args.compare)
    elif args.attempt and args.case:
        value = audit_sources(args.attempt, args.case)
        from worker_exchange.media import audit
        root = Path(args.attempt)
        value["source_decode"] = audit(root / "raw.mkv", value["frames"],
                                       mapping_sha256=sha(root / "video_frames.jsonl"),
                                       receipt=root / "source-decode-receipt.json")
    else:
        p.error("Supply --compare LEFT RIGHT or --attempt PATH --case ID")
    Path(args.output).write_text(json.dumps(value, indent=2) + "\n")


if __name__ == "__main__":
    main()
