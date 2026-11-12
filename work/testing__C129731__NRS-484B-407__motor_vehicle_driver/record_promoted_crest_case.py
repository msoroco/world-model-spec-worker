"""Bind the first distinct crest placement/direction exact-case CPU proof."""

import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NAME = "canonical-at-approach-b"
CASE = HERE.name + "__crest__at_500ft__approach_to_crest__occluded_approach_b"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / ("diagnostic-" + NAME + "-manifest.json")).read_text())
    entry = manifest["cases"][0]
    build = json.loads((HERE / ("branch-proof-" + NAME) / "build-receipt.json").read_text())
    if (entry["case_id"] != CASE or sha(HERE / entry["construction"]) != entry["construction_sha256"] or
            build["construction_sha256"] != entry["construction_sha256"]):
        raise ValueError("Promoted crest case construction changed")
    attempt = ROOT / ".runtime-work/c129731-canonical-at-approach-b-compat-v3"
    compat = json.loads((attempt / "compatibility.json").read_text())
    negative = (attempt / "negative-analysis.log").read_text()
    saved_path = ROOT / ".runtime-work/c129731-canonical-at-approach-b-saved-command-v1.log"
    saved = json.loads(saved_path.read_text())
    if (compat.get("passed") is not True or compat.get("case_id") != CASE or
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
    copies = ((attempt / "compatibility.json", NAME + "-branch-compatibility.json"),
              (attempt / "negative-analysis.log", NAME + "-branch-negative-analysis.log"),
              (saved_path, NAME + "-branch-processing.json"))
    for source, target in copies:
        shutil.copyfile(source, HERE / target)
    report = {"case_id": CASE, "construction_sha256": entry["construction_sha256"],
              "diagnostic_manifest_sha256": sha(HERE / ("diagnostic-" + NAME + "-manifest.json")),
              "compatibility_sha256": sha(HERE / copies[0][1]),
              "negative_sha256": sha(HERE / copies[1][1]),
              "saved_processing_sha256": sha(HERE / copies[2][1]),
              "exact_cpu_path_passed": True, "canonical_comparison_pending": True,
              "physical_acceptance_claimed": False}
    (HERE / (NAME + "-proof.json")).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_id": CASE, "exact_cpu_path_passed": True,
                      "canonical_comparison_pending": True, "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
