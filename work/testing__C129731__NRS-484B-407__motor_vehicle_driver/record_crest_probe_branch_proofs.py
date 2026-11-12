"""Bind at/beyond crest placement and direction diagnostic receipts."""

import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NAMES = tuple(prefix + "-" + branch for prefix in ("at", "beyond")
              for branch in ("near-a", "near-b", "approach-a", "approach-b"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    rows = []
    for name in NAMES:
        probe = "at_500ft" if name.startswith("at-") else "beyond_500ft"
        manifest = json.loads((HERE / ("diagnostic-" + name + "-manifest.json")).read_text())
        entry = manifest["cases"][0]
        if entry["case_id"] != HERE.name + "__crest__" + probe:
            raise ValueError("Wrong crest probe case: " + name)
        construction = HERE / entry["construction"]
        if sha(construction) != entry["construction_sha256"]:
            raise ValueError("Changed crest probe construction: " + name)
        build = json.loads((HERE / ("branch-proof-" + name) / "build-receipt.json").read_text())
        if (build["case_id"] != entry["case_id"] or build["probe"] != probe or
                build["construction_sha256"] != entry["construction_sha256"] or
                build["physical_acceptance_claimed"] is not False):
            raise ValueError("Crest probe build receipt differs: " + name)
        output = ROOT / ".runtime-work" / ("c129731-" + name + "-compat-v1")
        compat = json.loads((output / "compatibility.json").read_text())
        negative = (output / "negative-analysis.log").read_text()
        saved_path = ROOT / ".runtime-work" / ("c129731-" + name + "-saved-command-v1.log")
        saved = json.loads(saved_path.read_text())
        if (compat.get("passed") is not True or compat.get("case_id") != entry["case_id"] or
                compat.get("construction_sha256") != entry["construction_sha256"] or
                not {"negative_case_source", "mandatory_observations", "final_decode", "lean_decoder"}
                <= set(compat.get("checks", [])) or
                "Missing required source: turn_history.jsonl" not in negative):
            raise ValueError("Crest probe compatibility/negative proof differs: " + name)
        if (saved.get("passed") is not True or saved.get("recorded_only") is not True or
                saved.get("originals_preserved") is not True or
                saved.get("physical_acceptance_claimed") is not False or
                saved.get("native_revision", {}).get("construction_sha256") != entry["construction_sha256"]):
            raise ValueError("Crest probe saved proof differs: " + name)
        copies = ((output / "compatibility.json", name + "-branch-compatibility.json"),
                  (output / "negative-analysis.log", name + "-branch-negative-analysis.log"),
                  (saved_path, name + "-branch-processing.json"))
        for source, target in copies:
            shutil.copyfile(source, HERE / target)
        rows.append({"name": name, "probe": probe,
                     "placement": build["placement"],
                     "occluded_direction": build["occluded_direction"],
                     "construction_sha256": entry["construction_sha256"],
                     "site_sha256": build["site_sha256"],
                     "compatibility_sha256": sha(HERE / copies[0][1]),
                     "negative_sha256": sha(HERE / copies[1][1]),
                     "saved_processing_sha256": sha(HERE / copies[2][1]),
                     "physical_acceptance_claimed": False})
    report = {"status": "cpu_diagnostic_only", "branches": rows,
              "all_eight_exact_software_paths_passed": True,
              "physical_acceptance_claimed": False}
    (HERE / "crest-probe-branch-proof-index.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"branches": len(rows), "software_paths_passed": True,
                      "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
