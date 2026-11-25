"""Independently bind the selected traffic comparison to public and saved receipts."""
import hashlib
import json
import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT = runpy.run_path(str(HERE / "native/zone/audit_traffic_sources.py"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def case(condition):
    prefix = "selected-traffic-" + condition
    fixture = HERE / (prefix + "-fixture")
    raw = fixture / "native-raw-actors.jsonl"
    frames = fixture / "video_frames.jsonl"
    review = fixture / "review.json"
    measurement = AUDIT["measure"](raw, frames, review)
    public = read(HERE / (prefix + "-compatibility.json"))
    saved = read(HERE / (prefix + "-processing.json"))
    selected = public["measurement_examples"]["traffic_response"]
    case_id = HERE.name + "__traffic_" + condition
    if (public.get("passed") is not True or saved.get("passed") is not True or
            public["case_id"] != case_id or measurement["case_id"] != case_id or
            public["candidate_id"] != "primary" or saved["candidate_id"] != "primary" or
            public["construction_sha256"] != sha(HERE / (prefix + "-construction.json")) or
            saved["timestamp_joins"].get("frames") != 600 or
            not saved["originals_preserved"] or
            selected["value"]["following_speed_drop_mps"] != measurement["following_speed_drop_mps"] or
            selected["value"]["first_stripe_body_frame"] != measurement["first_stripe_body_frame"] or
            selected["value"]["first_adjoining_road_frame"] != measurement["first_adjoining_road_frame"] or
            selected["value"]["first_left_indicator_frame"] != measurement["first_left_indicator_frame"] or
            selected["sources"]["native-raw-actors.jsonl"] != sha(raw) or
            selected["sources"]["video_frames.jsonl"] != sha(frames) or
            selected["sources"]["review.json"] != sha(review)):
        raise ValueError("Selected traffic source, measurement or saved receipt differs")
    return {"case_id": case_id, "independent_measurement": measurement,
            "construction_sha256": sha(HERE / (prefix + "-construction.json")),
            "manifest_sha256": sha(HERE / (prefix + "-manifest.json")),
            "compatibility_sha256": sha(HERE / (prefix + "-compatibility.json")),
            "saved_processing_sha256": sha(HERE / (prefix + "-processing.json"))}


def main():
    clear = case("clear_traffic")
    response = case("following_brake")
    compared = AUDIT["compare"](clear["independent_measurement"],
                                response["independent_measurement"])
    if (clear["independent_measurement"]["following_speed_drop_mps"] != 0 or
            response["independent_measurement"]["following_speed_drop_mps"] != 1):
        raise ValueError("Selected traffic response magnitude differs")
    result = {"format": "c109137-selected-traffic-pair-proof-v1", "passed": True,
              "cases": [clear, response], "comparison": compared,
              "source_only": True, "original_native_observed": False,
              "physical_causation_or_legal_impediment_claimed": False}
    output = HERE / "selected-traffic-pair-proof.json"
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "case_count": 2, "receipt_sha256": sha(output)}))


if __name__ == "__main__":
    main()
