"""Audit original route sources and saved processing before local acceptance."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode", "actual_pixels", "physical_completion")
SOURCES = ("property-route-native.jsonl", "property-survey.json", "purpose-declaration.json",
           "trace.jsonl", "video_frames.jsonl", "capture/evidence.jsonl", "capture/manifest.json",
           *(name + ".mkv" for name in CAMERAS))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(case, candidate, attempt, processing, diagnostic):
    manifest = read(HERE / "execution-manifest.json")
    entry = next((e for e in manifest["cases"] if e["case_id"] == case), None)
    if entry is None:
        raise ValueError("Unselected delivery case")
    selected = entry if candidate == "primary" else next((x for x in entry["candidates"] if x["id"] == candidate), None)
    if selected is None or sha(HERE / selected["construction"]) != selected["construction_sha256"]:
        raise ValueError("Selected construction changed")
    selection = read(attempt / "candidate-selection.json")
    if selection["case_id"] != case or selection["candidate_id"] != candidate or selection["construction_sha256"] != selected["construction_sha256"]:
        raise ValueError("Candidate selection differs")
    proof = read(processing)
    if (proof.get("case_id") != case or proof.get("candidate_id") != candidate
            or proof.get("passed") is not True or proof.get("recorded_only") is not True
            or proof.get("originals_preserved") is not True or proof.get("missing_evidence")
            or proof.get("final_video_checks", {}).get("passed") is not True
            or proof.get("timestamp_joins", {}).get("frames") != 600
            or proof.get("physical_acceptance_claimed") or proof.get("legal_acceptance_claimed")):
        raise ValueError("Saved source proof incomplete")
    hashes = {}
    for name in SOURCES:
        path = attempt / name
        if not path.is_file():
            raise ValueError("Missing original source: " + name)
        hashes[name] = sha(path)
        if proof["original_source_hashes"].get(name) != hashes[name]:
            raise ValueError("Saved original source changed: " + name)
    native, trace, frames = (rows(attempt / name) for name in ("property-route-native.jsonl", "trace.jsonl", "video_frames.jsonl"))
    evidence = rows(attempt / "capture/evidence.jsonl")
    if not all(len(group) == 600 for group in (native, trace, frames, evidence)):
        raise ValueError("Original source frame count differs")
    for a, b, c, d in zip(native, trace, frames, evidence):
        frame = c["carla_frame"]
        if (a["native_frame"] != frame or b["frame"] != frame or d["original_frame"] != frame
                or abs(a["t_s"] - c["time_s"]) > 1e-8
                or abs(b["time_s"] - c["time_s"]) > 1e-8
                or abs(d["recording_time_s"] - c["time_s"]) > 1e-8):
            raise ValueError("Original source frame join differs")
    survey = read(attempt / "property-survey.json")
    purpose = read(attempt / "purpose-declaration.json")
    if not survey.get("source_kind") or not purpose.get("source_kind"):
        raise ValueError("Independent survey/purpose source missing")
    if diagnostic:
        if not read(attempt / "capture/manifest.json").get("synthetic_diagnostic"):
            raise ValueError("Diagnostic source kind changed")
        return {"case_id": case, "candidate_id": candidate, "accepted": False,
                "diagnostic_only": True, "source_sha256": hashes,
                "checks": {name: name in ("all_participants", "time_join", "full_video_decode") for name in CHECKS}}
    if read(attempt / "capture/manifest.json").get("synthetic_diagnostic"):
        raise ValueError("Original Native source required")
    if selection.get("manifest_sha256") != sha(HERE / "execution-manifest.json"):
        raise ValueError("Native manifest binding changed")
    review = attempt / "independent-physical-review.json"
    if not review.is_file() or read(review).get("passed") is not True:
        raise ValueError("Independent physical and pixel review required")
    checked = read(review)
    required = ("red_lens_facing_verified", "property_boundary_verified", "cross_street_entry_verified",
                "route_purpose_source_verified", "actual_pixels_verified")
    if any(checked.get(key) is not True for key in required):
        raise ValueError("Independent source review incomplete")
    return {"case_id": case, "candidate_id": candidate, "accepted": True,
            "source_sha256": hashes, "checks": {name: True for name in CHECKS}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("case", "candidate", "attempt", "processing", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    outcome = audit(args.case, args.candidate, Path(args.attempt), Path(args.processing), args.diagnostic)
    Path(args.output).write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_id": args.case, "accepted": outcome["accepted"], "diagnostic_only": args.diagnostic}))
