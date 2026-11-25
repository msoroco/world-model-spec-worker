"""Independent source and software audit for one selected C111250 case.

Synthetic fixtures prove checks run. Original pixels, official facility status,
subsection (3) legal applicability and physical completion await local capture.
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(case, remove_native_source=False):
    if case not in (HERE.name + "__controlled_1", HERE.name + "__controlled_2"):
        raise ValueError("Unknown selected exact case")
    suffix = case.rsplit("__", 1)[1]
    source = HERE / ("native-diagnostic-" + suffix + "-sources")
    recipe = read(HERE / ("native-diagnostic-" + suffix + "-recipe.json"))
    spec = HERE / ("native-diagnostic-" + suffix + "-spec.json")
    if recipe["generator"]["sha256"] != sha(spec):
        raise ValueError("Selected recipe/source hash differs")
    required = ("facility-context.json", "subsection3-context.json",
                "body-history.jsonl", "trace.jsonl", "video_frames.jsonl",
                "capture/evidence.jsonl", "road.xodr")
    for name in required:
        if (remove_native_source and name == "body-history.jsonl") or not (source / name).is_file():
            raise ValueError("Missing required source: " + name)
    body, trace, frames = (rows(source / name) for name in
                           ("body-history.jsonl", "trace.jsonl", "video_frames.jsonl"))
    if len(body) != 600 or len(trace) != 600 or len(frames) != 600:
        raise ValueError("Selected source duration differs")
    for index, (one, two, three) in enumerate(zip(body, trace, frames)):
        if (one["native_frame"] != index or two["frame"] != index or
                three["native_frame"] != index or three["video_frame"] != index or
                abs(one["time_s"] - index / 20) > 1e-6 or
                abs(two["time_s"] - index / 20) > 1e-6 or
                abs(three["time_s"] - index / 20) > 1e-6 or
                len(one["body_xy_m"]) != 4 or one["speed_mps"] <= 0):
            raise ValueError("Original-shaped full body/time join differs")
    manifest = read(HERE / "execution-manifest.json")
    entry = next(item for item in manifest["cases"] if item["case_id"] == case)
    compat = read(HERE / ("selected-" + suffix + "-primary-compatibility.json"))
    saved = read(HERE / ("selected-" + suffix + "-primary-processing.json"))
    if (compat["case_id"] != case or compat["construction_sha256"] != entry["construction_sha256"]
            or compat["fixture_recipe_sha256"] != sha(HERE / ("native-diagnostic-" + suffix + "-recipe.json"))
            or compat["fixture_manifest"]["body-history.jsonl"] != sha(source / "body-history.jsonl")
            or not compat["passed"] or compat["negative_removed"] != "body-history.jsonl"
            or {name + ".mkv" for name in CAMERAS} - set(compat["fixture_manifest"])):
        raise ValueError("Compatibility/source binding differs")
    if (not saved["recorded_only"] or not saved["originals_preserved"]
            or saved["missing_evidence"] or saved["case_id"] != case
            or saved["analysis_revision"]["construction_sha256"] != entry["construction_sha256"]
            or not saved["final_video_checks"]["passed"]
            or saved["final_video_checks"]["frames"] != 600
            or saved["physical_acceptance_claimed"] or saved["legal_acceptance_claimed"]):
        raise ValueError("Recorded-only proof differs")
    physical = read(HERE / ("physical-" + suffix + "-proof.json"))
    if physical["construction_sha256"] != entry["construction_sha256"]:
        raise ValueError("Physical fixture proof changed")
    return {"passed": True, "case_id": case, "source_frames": 600,
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "scope": "synthetic CPU source and receipt audit only; local Native pixels and completion pending",
            "accepted": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--remove-native-source", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.remove_native_source), indent=2))
