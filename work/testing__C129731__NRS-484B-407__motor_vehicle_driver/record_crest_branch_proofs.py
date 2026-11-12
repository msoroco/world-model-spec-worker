"""Bind the four crest placement/direction CPU diagnostic proof receipts."""

import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VERSIONS = {"near-a": "v2", "near-b": "v2", "approach-a": "v2", "approach-b": "v5"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    rows = []
    for name, version in VERSIONS.items():
        manifest = json.loads((HERE / ("diagnostic-" + name + "-manifest.json")).read_text())
        entry = manifest["cases"][0]
        construction_path = HERE / entry["construction"]
        if sha(construction_path) != entry["construction_sha256"]:
            raise ValueError("Branch construction changed: " + name)
        output = ROOT / ".runtime-work" / ("c129731-" + name + "-compat-" + version)
        saved_log = ROOT / ".runtime-work" / ("c129731-" + name + "-saved-command-v2.log")
        compat = json.loads((output / "compatibility.json").read_text())
        saved = json.loads(saved_log.read_text())
        if not (compat.get("passed") is True and
                compat.get("case_id") == entry["case_id"] and
                compat.get("construction_sha256") == entry["construction_sha256"] and
                {"negative_case_source", "mandatory_observations", "final_decode", "lean_decoder"}
                <= set(compat.get("checks", []))):
            raise ValueError("Branch compatibility receipt differs: " + name)
        negative = (output / "negative-analysis.log").read_text()
        if "Missing required source: turn_history.jsonl" not in negative:
            raise ValueError("Missing negative source rejection: " + name)
        if not (saved.get("passed") is True and saved.get("recorded_only") is True and
                saved.get("originals_preserved") is True and
                saved.get("physical_acceptance_claimed") is False and
                saved.get("native_revision", {}).get("construction_sha256") == entry["construction_sha256"]):
            raise ValueError("Branch saved-processing receipt differs: " + name)
        stem = "approach-branch" if name == "approach-b" else name + "-branch"
        copies = ((output / "compatibility.json", stem + "-compatibility.json"),
                  (output / "negative-analysis.log", stem + "-negative-analysis.log"),
                  (saved_log, stem + "-processing.json"))
        for source, target in copies:
            shutil.copyfile(source, HERE / target)
        build = json.loads((HERE / ("branch-proof-" + name) / "build-receipt.json").read_text())
        if build["construction_sha256"] != entry["construction_sha256"]:
            raise ValueError("Branch build receipt differs: " + name)
        rows.append({"name": name, "placement": build["placement"],
                     "occluded_direction": build["occluded_direction"],
                     "construction_sha256": entry["construction_sha256"],
                     "compatibility_sha256": sha(HERE / copies[0][1]),
                     "negative_sha256": sha(HERE / copies[1][1]),
                     "saved_processing_sha256": sha(HERE / copies[2][1]),
                     "diagnostic_fixture": True, "physical_acceptance_claimed": False})
    report = {"status": "cpu_diagnostic_only", "case_id": rows and entry["case_id"],
              "branches": rows, "all_four_exact_software_paths_passed": True,
              "physical_acceptance_claimed": False}
    (HERE / "crest-branch-proof-index.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"branches": len(rows), "software_paths_passed": True,
                      "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
