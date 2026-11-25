"""Independent source-only fixed-condition audit of the two crossing cases."""

import argparse
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT = "training__C109166__NRS-484B-287-1c__pedestrian"
CASES = ("marked_crosswalk", "unmarked_midblock")


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError("Missing comparison source: " + name)
    return path


def read(root, name):
    return json.loads(required(root, name).read_text())


def rows(root, name):
    return [json.loads(line) for line in required(root, name).read_text().splitlines()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(marked, unmarked):
    folders = (Path(marked), Path(unmarked))
    configs = [read(folder, "config.json") for folder in folders]
    for config, case in zip(configs, CASES):
        if config.get("case_id") != ASSIGNMENT + "__" + case:
            raise ValueError("Comparison names another exact crossing case")
    fixed_keys = ("assignment_id", "cell_id", "law_id", "actor", "rate_hz",
                  "duration_s", "frames", "candidate_id", "camera_dimensions",
                  "detail_camera_height_m", "required_atoms", "physical_completion")
    for key in fixed_keys:
        if configs[0].get(key) is None or configs[0].get(key) != configs[1].get(key):
            raise ValueError("Comparison fixed condition differs: " + key)
    for source in ("native-survey.json", "exception-applicability-source.json"):
        if sha(required(folders[0], source)) != sha(required(folders[1], source)):
            raise ValueError("Comparison fixed source differs: " + source)
    maps = [rows(folder, "video_frames.jsonl") for folder in folders]
    people = [rows(folder, "pedestrian-original.jsonl") for folder in folders]
    controls = [rows(folder, "controls-original.jsonl") for folder in folders]
    camera_rows = [rows(folder, "camera-sources.jsonl") for folder in folders]
    if any(len(group) != 600 for set_of_rows in (maps, people, controls)
           for group in set_of_rows) or any(len(group) != 2400 for group in camera_rows):
        raise ValueError("Comparison requires full original source duration")
    observed_deltas = []
    for index in range(600):
        times = [group[index]["time_s"] for group in maps]
        if abs(times[0] - times[1]) > 0.05:
            raise ValueError("Comparison event timing differs")
        states = [tuple((item["native_actor_id"], item["native_state"],
                         item["operating_observed"]) for item in group[index]["controls"])
                  for group in controls]
        if states[0] != states[1]:
            raise ValueError("Comparison official control state differs")
        centers = [group[index]["center_xy_m"] for group in people]
        if abs(centers[0][1] - centers[1][1]) > 0.25:
            raise ValueError("Comparison pedestrian approach profile differs")
        observed_deltas.append(centers[1][0] - centers[0][0])
        for camera_index in range(4):
            pair = [group[index * 4 + camera_index] for group in camera_rows]
            fixed = ("camera", "video_frame", "width", "height")
            if any(pair[0].get(key) != pair[1].get(key) for key in fixed):
                raise ValueError("Comparison camera plan differs")
    if not all(math.isfinite(delta) and abs(delta - 20.0) <= 0.25 for delta in observed_deltas):
        raise ValueError("Comparison crossing-location difference not isolated")
    return {"format": "c109166-287-1c-source-comparison-v1",
            "case_ids": [config["case_id"] for config in configs],
            "fixed_conditions_checked": list(fixed_keys) + [
                "survey", "exception context", "600 relative times", "two control states",
                "pedestrian approach profile", "four-camera plan"],
            "deliberate_difference": "crossing_location",
            "observed_x_separation_m": [min(observed_deltas), max(observed_deltas)],
            "source_sha256": {str(folder): {name: sha(required(folder, name)) for name in
                               ("config.json", "native-survey.json", "video_frames.jsonl",
                                "pedestrian-original.jsonl", "controls-original.jsonl",
                                "camera-sources.jsonl")} for folder in folders},
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--marked", required=True)
    parser.add_argument("--unmarked", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("Retain prior comparison audit")
    result = audit(args.marked, args.unmarked)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"case_ids": result["case_ids"], "fixed": len(result["fixed_conditions_checked"])}))


if __name__ == "__main__":
    main()
