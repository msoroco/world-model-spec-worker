"""Independent source check for the selected adjoining-highway crossing pair."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def events(raw_path, frame_path):
    actors, mapping = rows(raw_path), rows(frame_path)
    if len(actors) != 600 or len(mapping) != 600:
        raise ValueError("Selected crossing pair needs complete 600-frame sources")
    stripe = adjoining = signal = None
    first_native = actors[0]["native_frame"]
    for index, (actor, frame) in enumerate(zip(actors, mapping)):
        if (actor.get("frame") != index or frame.get("video_frame") != index or
                actor.get("native_frame") != first_native + index or
                frame.get("native_frame") != first_native + index or
                abs(actor.get("time_s", -1) - frame.get("time_s", -2)) > 1e-6):
            raise ValueError("Selected crossing Native/video join differs")
        body = actor.get("ego", {}).get("body_native_xyz_m")
        if not isinstance(body, list) or len(body) != 8:
            raise ValueError("Selected crossing full body absent")
        if stripe is None and min(p[1] for p in body) <= 0 <= max(p[1] for p in body) and max(p[0] for p in body) >= 0 and min(p[0] for p in body) <= 55:
            stripe = index
        if adjoining is None and actor.get("observed_road_id") == 218 and actor.get("observed_lane_id") == -1:
            adjoining = index
        observed_signal = actor.get("observed_left_indicator")
        if type(observed_signal) is not bool or bool(actor["ego"]["light_state"] & 32) != observed_signal:
            raise ValueError("Selected crossing observed indicator source differs")
        if signal is None and observed_signal:
            signal = index
    if stripe is None or adjoining is None:
        raise ValueError("Selected crossing/adjoining event absent")
    return {"first_stripe_body_frame": stripe,
            "first_adjoining_road_frame": adjoining,
            "first_left_indicator_frame": signal}


def main():
    records = []
    for suffix in ("probe1", "probe2"):
        fixture = HERE / ("selected-" + suffix + "-fixture")
        raw = fixture / "native-raw-actors.jsonl"
        mapping = fixture / "video_frames.jsonl"
        review_path = fixture / "review.json"
        review = json.loads(review_path.read_text())
        if review["raw_sha256"] != sha(raw) or review["video_frames_sha256"] != sha(mapping):
            raise ValueError("Selected fixture review source hash differs")
        measured = events(raw, mapping)
        public = json.loads((HERE / ("selected-" + suffix + "-compatibility.json")).read_text())
        selected = public["measurement_examples"]["adjoining_crossing"]
        if (public.get("passed") is not True or public["case_id"] != review["case_id"] or
                selected["sources"]["native-raw-actors.jsonl"] != sha(raw) or
                selected["sources"]["video_frames.jsonl"] != sha(mapping) or
                selected["sources"]["review.json"] != sha(review_path) or
                any(selected["value"][key] != value for key, value in measured.items())):
            raise ValueError("Selected public measurement/source differs")
        records.append({"case_id": public["case_id"], "source_sha256": {
            "native-raw-actors.jsonl": sha(raw), "video_frames.jsonl": sha(mapping),
            "review.json": sha(review_path)}, "independent_events": measured,
            "compatibility_receipt_sha256": sha(HERE / ("selected-" + suffix + "-compatibility.json"))})
    first, second = (record["independent_events"] for record in records)
    if any(first[key] != second[key] for key in ("first_stripe_body_frame", "first_adjoining_road_frame")):
        raise ValueError("Selected pair changed fixed crossing geometry")
    if first["first_left_indicator_frame"] is None or second["first_left_indicator_frame"] is not None:
        raise ValueError("Selected pair lacks observed indicator difference")
    proof = {"format": "c109137-selected-crossing-source-pair-v1", "records": records,
             "fixed_conditions": ["first stripe body frame", "first adjoining road frame"],
             "deliberate_difference": "observed prior left indicator",
             "original_native_observed": False, "legal_verdict_claimed": False, "passed": True}
    output = HERE / "selected-crossing-pair-proof.json"
    output.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "case_count": 2, "receipt_sha256": sha(output)}))


if __name__ == "__main__":
    main()
