"""Retain exact source-bound CPU receipts for one curve direction case."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SHORT = {"short_of_500ft": "short", "at_500ft": "at", "beyond_500ft": "beyond"}
CHECKS = {"negative_case_source", "mandatory_observations", "final_decode", "lean_decoder"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(probe, direction):
    name = "canonical-curve-" + SHORT[probe] + "-" + ("a" if direction == "approach_a" else "b")
    case_id = HERE.name + "__curve__" + probe + "__occluded_" + direction
    manifest_path = HERE / ("diagnostic-" + name + "-manifest.json")
    entry = json.loads(manifest_path.read_text())["cases"][0]
    build = json.loads((HERE / ("branch-proof-" + name) / "build-receipt.json").read_text())
    if (entry["case_id"] != case_id or build["case_id"] != case_id or
            sha(HERE / entry["construction"]) != entry["construction_sha256"] or
            build["construction_sha256"] != entry["construction_sha256"] or
            build["occluded_direction"] != direction):
        raise ValueError("Curve exact construction changed")
    attempt = ROOT / ".runtime-work" / ("c129731-" + name + "-compat-v1")
    compat = json.loads((attempt / "compatibility.json").read_text())
    negative = (attempt / "negative-analysis.log").read_text()
    saved_path = ROOT / ".runtime-work" / ("c129731-" + name + "-saved-command-v1.log")
    saved = json.loads(saved_path.read_text())
    if (compat.get("passed") is not True or compat.get("case_id") != case_id or
            compat.get("construction_sha256") != entry["construction_sha256"] or
            not CHECKS <= set(compat.get("checks", [])) or
            compat.get("negative_log_sha256") != sha(attempt / "negative-analysis.log") or
            "Missing required source: turn_history.jsonl" not in negative):
        raise ValueError("Curve compatibility/negative source proof differs")
    if (saved.get("passed") is not True or saved.get("recorded_only") is not True or
            saved.get("originals_preserved") is not True or
            saved.get("physical_acceptance_claimed") is not False or
            saved.get("native_revision", {}).get("construction_sha256") != entry["construction_sha256"]):
        raise ValueError("Curve saved proof differs")
    copies = ((attempt / "compatibility.json", name + "-branch-compatibility.json"),
              (attempt / "negative-analysis.log", name + "-branch-negative-analysis.log"),
              (saved_path, name + "-branch-processing.json"))
    for source, target in copies:
        shutil.copyfile(source, HERE / target)
    report = {"case_id": case_id, "construction_sha256": entry["construction_sha256"],
              "diagnostic_manifest_sha256": sha(manifest_path),
              "compatibility_sha256": sha(HERE / copies[0][1]),
              "negative_sha256": sha(HERE / copies[1][1]),
              "saved_processing_sha256": sha(HERE / copies[2][1]),
              "exact_cpu_path_passed": True, "canonical_comparison_pending": True,
              "physical_acceptance_claimed": False}
    (HERE / (name + "-proof.json")).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_id": case_id, "exact_cpu_path_passed": True,
                      "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", choices=tuple(SHORT), required=True)
    parser.add_argument("--direction", choices=("approach_a", "approach_b"), required=True)
    arguments = parser.parse_args()
    main(arguments.probe, arguments.direction)
