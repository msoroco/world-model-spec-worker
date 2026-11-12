"""Bind the first distinct crest placement/direction exact-case CPU proof."""

import hashlib
import json
import shutil
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--placement", choices=("near_summit", "approach_to_crest"), default="approach_to_crest")
    parser.add_argument("--direction", choices=("approach_a", "approach_b"), default="approach_b")
    parser.add_argument("--probe", choices=("short_of_500ft", "at_500ft", "beyond_500ft"), default="at_500ft")
    parser.add_argument("--compat-version", type=int, default=1)
    parser.add_argument("--saved-version", type=int, default=1)
    args = parser.parse_args()
    suffix = {"short_of_500ft": "short", "at_500ft": "at", "beyond_500ft": "beyond"}[args.probe]
    name = "canonical-" + suffix + "-" + ("near" if args.placement == "near_summit" else "approach") + ("-a" if args.direction == "approach_a" else "-b")
    case = HERE.name + "__crest__" + args.probe + "__" + args.placement + "__occluded_" + args.direction
    manifest_path = HERE / ("diagnostic-" + name + "-manifest.json")
    manifest = json.loads(manifest_path.read_text())
    entry = manifest["cases"][0]
    build = json.loads((HERE / ("branch-proof-" + name) / "build-receipt.json").read_text())
    if (entry["case_id"] != case or sha(HERE / entry["construction"]) != entry["construction_sha256"] or
            build["construction_sha256"] != entry["construction_sha256"] or build["case_id"] != case):
        raise ValueError("Promoted crest case construction changed")
    attempt = ROOT / (".runtime-work/c129731-" + name + "-compat-v" + str(args.compat_version))
    compat = json.loads((attempt / "compatibility.json").read_text())
    negative = (attempt / "negative-analysis.log").read_text()
    saved_path = ROOT / (".runtime-work/c129731-" + name + "-saved-command-v" + str(args.saved_version) + ".log")
    saved = json.loads(saved_path.read_text())
    if (compat.get("passed") is not True or compat.get("case_id") != case or
            compat.get("construction_sha256") != entry["construction_sha256"] or
            not {"negative_case_source", "mandatory_observations", "final_decode", "lean_decoder"}
            <= set(compat.get("checks", [])) or
            "Missing required source: turn_history.jsonl" not in negative):
        raise ValueError("Promoted crest compatibility/negative proof differs")
    if (saved.get("passed") is not True or saved.get("recorded_only") is not True or
            saved.get("originals_preserved") is not True or
            saved.get("physical_acceptance_claimed") is not False or
            saved.get("native_revision", {}).get("construction_sha256") != entry["construction_sha256"]):
        raise ValueError("Promoted crest saved proof differs")
    copies = ((attempt / "compatibility.json", name + "-branch-compatibility.json"),
              (attempt / "negative-analysis.log", name + "-branch-negative-analysis.log"),
              (saved_path, name + "-branch-processing.json"))
    for source, target in copies:
        shutil.copyfile(source, HERE / target)
    report = {"case_id": case, "construction_sha256": entry["construction_sha256"],
              "diagnostic_manifest_sha256": sha(manifest_path),
              "compatibility_sha256": sha(HERE / copies[0][1]),
              "negative_sha256": sha(HERE / copies[1][1]),
              "saved_processing_sha256": sha(HERE / copies[2][1]),
              "exact_cpu_path_passed": True, "canonical_comparison_pending": True,
              "physical_acceptance_claimed": False}
    (HERE / (name + "-proof.json")).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_id": case, "exact_cpu_path_passed": True,
                      "canonical_comparison_pending": True, "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
