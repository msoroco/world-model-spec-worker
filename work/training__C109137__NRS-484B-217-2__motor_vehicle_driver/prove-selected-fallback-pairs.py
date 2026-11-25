"""Independently compare both selected crossing cases at each fallback policy."""
import hashlib
import json
import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVENTS = runpy.run_path(str(HERE / "prove-selected-crossing-pair.py"))["events"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def check_case(probe, candidate):
    prefix = f"selected-probe{probe}-{candidate}"
    fixture = HERE / (prefix + "-fixture")
    raw = fixture / "native-raw-actors.jsonl"
    frames = fixture / "video_frames.jsonl"
    review_path = fixture / "review.json"
    review = read(review_path)
    manifest_path = HERE / (prefix + "-manifest.json")
    construction_path = HERE / (prefix + "-construction.json")
    public_path = HERE / (prefix + "-compatibility.json")
    saved_path = HERE / (prefix + "-processing.json")
    public, saved = read(public_path), read(saved_path)
    selected = public["measurement_examples"]["adjoining_crossing"]
    observed = EVENTS(raw, frames)
    case_id = HERE.name + f"__probe_{probe}"
    if review["raw_sha256"] != sha(raw) or review["video_frames_sha256"] != sha(frames):
        raise ValueError("Fallback review source hashes differ")
    if review["case_id"] != case_id or review["candidate_id"] != candidate:
        raise ValueError("Fallback review identity differs")
    if (public["case_id"] != case_id or public["candidate_id"] != candidate or
            public["construction_sha256"] != sha(construction_path) or
            not public["passed"] or not saved["passed"] or
            saved["candidate_id"] != candidate or
            not saved["originals_preserved"] or
            saved["timestamp_joins"] != {"frames": 600, "passed": True,
                                          "missing_original_trace_or_map": False}):
        raise ValueError("Fallback public or saved receipt differs")
    if any(selected["sources"][name] != sha(fixture / name)
           for name in ("native-raw-actors.jsonl", "video_frames.jsonl", "review.json")):
        raise ValueError("Fallback public source binding differs")
    if any(selected["value"][key] != value for key, value in observed.items()):
        raise ValueError("Fallback public measurement differs from independent events")
    manifest = read(manifest_path)
    candidate_entry = manifest["cases"][0]["candidates"]
    if (len(candidate_entry) != 1 or candidate_entry[0]["id"] != candidate or
            candidate_entry[0]["construction_sha256"] != sha(construction_path)):
        raise ValueError("Fallback manifest construction differs")
    return {"case_id": case_id, "candidate_id": candidate,
            "source_hashes": {name: sha(fixture / name)
                              for name in ("native-raw-actors.jsonl", "video_frames.jsonl", "review.json")},
            "independent_events": observed,
            "manifest_sha256": sha(manifest_path),
            "compatibility_sha256": sha(public_path),
            "saved_processing_sha256": sha(saved_path)}


def main():
    pairs = []
    for candidate in ("fallback1", "fallback2"):
        first, second = (check_case(probe, candidate) for probe in (1, 2))
        a, b = first["independent_events"], second["independent_events"]
        if (a["first_stripe_body_frame"] != b["first_stripe_body_frame"] or
                a["first_adjoining_road_frame"] != b["first_adjoining_road_frame"] or
                a["first_left_indicator_frame"] != 60 or
                b["first_left_indicator_frame"] is not None):
            raise ValueError("Fallback controlled pair changed fixed conditions or indicator")
        pairs.append({"candidate_id": candidate, "records": [first, second]})
    proof = {"format": "c109137-selected-fallback-source-pairs-v1",
             "pairs": pairs, "passed": True,
             "scope": "synthetic current-runtime source, public compatibility and saved-only processing",
             "original_native_observed": False, "physical_or_legal_acceptance": False}
    output = HERE / "selected-fallback-pairs-proof.json"
    output.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "pair_count": 2,
                      "receipt_sha256": sha(output)}))


if __name__ == "__main__":
    main()
