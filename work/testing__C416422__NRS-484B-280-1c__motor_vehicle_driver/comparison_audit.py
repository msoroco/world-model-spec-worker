"""Independent paired audit of fixed conditions and measured response difference."""
import argparse
import json
from pathlib import Path


FIXED = ("law_id", "cell_id", "actor_id", "map_sha256", "road_site_sha256",
         "fixed_scene_sha256", "participant_classes", "camera_contract_sha256", "duration_s")


def audit(prompt, deferred):
    if (not prompt.get("case_id", "").endswith("__prompt_brake") or
            not deferred.get("case_id", "").endswith("__deferred_brake")):
        raise ValueError("wrong exact response comparison cases")
    for key in FIXED:
        if not prompt.get(key) or not deferred.get(key):
            raise ValueError("missing fixed condition: " + key)
        if prompt[key] != deferred[key]:
            raise ValueError("fixed condition differs: " + key)
    for record, policy in ((prompt, "prompt_brake"), (deferred, "deferred_brake")):
        if record.get("format") != "worker-delivery-audit" or record.get("passed") is not True:
            raise ValueError("source-audited delivery receipt missing")
        if record.get("response_policy") != policy:
            raise ValueError("declared response policy differs from exact case")
        if not all(record.get(key) for key in
                   ("native_result_sha256", "frame_map_sha256", "video_sha256", "source_decode_receipt_sha256")):
            raise ValueError("missing original saved-media binding")
        measurement = record.get("measurement", {})
        if measurement.get("format") != "worker-near-road-pedestrian-measurements" or not all(
            measurement.get("sources", {}).get(name) for name in
            ("road-site.json", "map.xodr", "encounter-history.jsonl", "video_frames.jsonl")
        ):
            raise ValueError("missing source-bound pedestrian measurement")
        if measurement.get("frame_count") != record.get("frame_count") or measurement.get("first_observation") is None:
            raise ValueError("incomplete original observation/frame history")
        if measurement.get("legal_proper_caution_verdict") != "unresolved" or measurement.get("legal_near_road_verdict") != "unresolved" or record.get("legal_verdict") is not None:
            raise ValueError("comparison asserted legal proper caution")
        if record.get("human_observation_claimed") is not False:
            raise ValueError("scripted input misrepresented as human cognition")
    first = prompt["measurement"].get("observed_response_delay_s")
    second = deferred["measurement"].get("observed_response_delay_s")
    if first is None or second is None or not first < second:
        raise ValueError("declared brake-response difference not physically observed")
    return {"comparison_id": "near_road_response_timing", "passed": True,
            "fixed_conditions": list(FIXED),
            "difference": "original measured scripted-driver brake response delay",
            "prompt_response_delay_s": first, "deferred_response_delay_s": second,
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
