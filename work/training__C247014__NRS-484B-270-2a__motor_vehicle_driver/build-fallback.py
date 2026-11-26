"""Author a slower, earlier-lane-transition Native fallback for each exact case."""

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SUFFIXES = ("witness_1", "witness_2", "exception_1_1", "exception_1_2",
            "exception_unsafe_available")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=SUFFIXES)
    args = parser.parse_args()
    path = HERE / "selected-native-draft-manifest.json"
    manifest = json.loads(path.read_text())
    selected_suffixes = (args.only,) if args.only else SUFFIXES
    for suffix in selected_suffixes:
        case_id = HERE.name + "__" + suffix
        entry = next(e for e in manifest["cases"] if e["case_id"] == case_id)
        construction = json.loads((HERE / entry["construction"]).read_text())
        files = construction["files"]
        config_file = next(f for f in files if f["path"] == "config.json")
        config = json.loads(config_file["content"])
        config["candidate_id"] = "fallback1"
        config_file["content"] = json.dumps(config, indent=2) + "\n"
        scene = next(f for f in files if f["path"] == "scene.py")
        source = scene["content"]
        if "ego_x = -40 + 3 * t" not in source or "(frame - 180) / 80" not in source:
            raise ValueError("Primary scene no longer matches reviewed fallback knobs")
        scene["content"] = (source.replace("ego_x = -40 + 3 * t", "ego_x = -40 + 2.8 * t")
                            .replace("(frame - 180) / 80", "(frame - 140) / 100"))
        construction["measurement_plan"]["candidate_id"] = "fallback1"
        construction["mechanisms"] = list(construction["mechanisms"]) + [
            "fallback requests 2.8 m/s longitudinal progress and an earlier, longer left transition"]
        construction["status"] = "fallback_cpu_draft_original_unobserved"
        fallback = HERE / "selected-native-draft" / suffix / "fallback1" / "construction.json"
        write(fallback, construction)
        entry["candidates"] = [{
            "id": "fallback1", "construction": str(fallback.relative_to(HERE)),
            "construction_sha256": sha(fallback),
            "trigger": {
                "source": "original participant-poses.jsonl and saved left_lane_occupancy channel",
                "metric": "subject lane occupancy before and throughout original body-overlap pass",
                "failure_condition": "primary attempt does not realize planned lane occupancy before and throughout the pass, or original passing motion is incomplete",
            },
            "changed_knobs": [
                "ego longitudinal target 3.0 to 2.8 m/s",
                "left-lane target transition frames 180-260 to 140-240",
            ],
        }]
    write(path, manifest)
    print(json.dumps({"candidate_count": len(selected_suffixes), "manifest_sha256": sha(path)}, sort_keys=True))


if __name__ == "__main__":
    main()
