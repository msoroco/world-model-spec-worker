"""Independent paired audit of fixed conditions and measured response difference."""
import argparse
import json
from pathlib import Path


FIXED = ("law_id", "cell_id", "actor_id", "crossing_geometry_sha256",
         "fixed_scene_sha256", "participant_classes", "camera_contract_sha256", "duration_s")


def audit(prompt, deferred):
    if (not prompt.get("case_id", "").endswith("__marked_crosswalk") or
            not deferred.get("case_id", "").endswith("__unmarked_crosswalk")):
        raise ValueError("wrong exact crossing comparison cases")
    for key in FIXED:
        if not prompt.get(key) or not deferred.get(key):
            raise ValueError("missing fixed condition: " + key)
        if prompt[key] != deferred[key]:
            raise ValueError("fixed condition differs: " + key)
    for record, kind in ((prompt, "marked"), (deferred, "unmarked")):
        if record.get("format") != "worker-delivery-audit" or record.get("passed") is not True:
            raise ValueError("source-audited delivery receipt missing")
        if record.get("crosswalk_kind") != kind or record.get("response_policy") != "fixed_brake":
            raise ValueError("declared crossing kind or fixed controller differs from exact case")
        if not all(record.get(key) for key in
                   ("native_result_sha256", "frame_map_sha256", "video_sha256", "source_decode_receipt_sha256")):
            raise ValueError("missing original saved-media binding")
        measurement = record.get("measurement", {})
        if measurement.get("format") != "worker-crosswalk-pedestrian-measurements" or not all(
            measurement.get("sources", {}).get(name) for name in
            ("crosswalk-site.json", "map.xodr", "encounter-history.jsonl", "video_frames.jsonl")
        ):
            raise ValueError("missing source-bound pedestrian measurement")
        if measurement.get("frame_count") != record.get("frame_count") or measurement.get("first_observation") is None:
            raise ValueError("incomplete original observation/frame history")
        if measurement.get("legal_proper_caution_verdict") != "unresolved" or measurement.get("legal_crosswalk_proximity_verdict") != "unresolved" or record.get("legal_verdict") is not None:
            raise ValueError("comparison asserted legal proper caution")
        if record.get("human_observation_claimed") is not False:
            raise ValueError("scripted input misrepresented as human cognition")
    if prompt["measurement"].get("crosswalk_kind") != "marked" or deferred["measurement"].get("crosswalk_kind") != "unmarked":
        raise ValueError("original crossing kind difference not measured")
    if not prompt["measurement"].get("pedestrian_in_crosswalk_frames") or not deferred["measurement"].get("pedestrian_in_crosswalk_frames"):
        raise ValueError("pedestrian crossing not realized")
    return {"comparison_id": "marked_vs_unmarked_crosswalk", "passed": True,
            "fixed_conditions": list(FIXED),
            "difference": "original measured crosswalk marking present versus absent",
            "marked_map_sha256": prompt["map_sha256"],
            "unmarked_map_sha256": deferred["map_sha256"],
            "human_observation_claimed": False, "legal_verdict": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    parser.add_argument("deferred")
    args = parser.parse_args()
    print(json.dumps(audit(json.loads(Path(args.prompt).read_text()),
                           json.loads(Path(args.deferred).read_text())), indent=2))


if __name__ == "__main__":
    main()
