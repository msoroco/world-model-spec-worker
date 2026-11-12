"""Retain source-bound CPU receipts for three exact-case controller fallbacks."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REQUIRED = {"negative_case_source", "mandatory_observations", "final_decode", "lean_decoder"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(name):
    primary = json.loads((HERE / ("diagnostic-" + name + "-manifest.json")).read_text())["cases"][0]
    manifest = json.loads((HERE / ("diagnostic-" + name + "-fallback-manifest.json")).read_text())
    entry = manifest["cases"][0]
    if entry["case_id"] != primary["case_id"] or entry["construction_sha256"] != primary["construction_sha256"]:
        raise ValueError("Fallback exact primary identity changed")
    if {c["id"] for c in entry["candidates"]} != {"fallback1", "fallback2", "fallback3"}:
        raise ValueError("Three distinct measured-risk fallbacks required")
    reports = []
    for candidate in entry["candidates"]:
        ident = candidate["id"]
        construction = HERE / candidate["construction"]
        attempt = ROOT / (".runtime-work/c129731-" + name + "-" + ident + "-compat-v1")
        saved_path = ROOT / (".runtime-work/c129731-" + name + "-" + ident + "-saved-command-v1.log")
        compatibility = json.loads((attempt / "compatibility.json").read_text())
        saved = json.loads(saved_path.read_text())
        negative = (attempt / "negative-analysis.log").read_text()
        if (sha(construction) != candidate["construction_sha256"] or
                compatibility.get("passed") is not True or compatibility.get("case_id") != entry["case_id"] or
                compatibility.get("candidate_id") != ident or
                compatibility.get("construction_sha256") != candidate["construction_sha256"] or
                not REQUIRED <= set(compatibility.get("checks", [])) or
                compatibility.get("negative_log_sha256") != sha(attempt / "negative-analysis.log") or
                "Missing required source: turn_history.jsonl" not in negative):
            raise ValueError("Fallback compatibility/negative proof differs: " + ident)
        if (saved.get("passed") is not True or saved.get("recorded_only") is not True or
                saved.get("originals_preserved") is not True or
                saved.get("physical_acceptance_claimed") is not False or
                saved.get("candidate_id") != ident or
                saved.get("native_revision", {}).get("construction_sha256") != candidate["construction_sha256"]):
            raise ValueError("Fallback saved-processing proof differs: " + ident)
        prefix = name + "-" + ident
        copies = ((attempt / "compatibility.json", prefix + "-compatibility.json"),
                  (attempt / "negative-analysis.log", prefix + "-negative-analysis.log"),
                  (saved_path, prefix + "-processing.json"))
        for source, target in copies:
            shutil.copyfile(source, HERE / target)
        reports.append({"id": ident, "construction": candidate["construction"],
                        "construction_sha256": candidate["construction_sha256"],
                        "changed_knobs": candidate["changed_knobs"], "trigger": candidate["trigger"],
                        "compatibility_sha256": sha(HERE / copies[0][1]),
                        "negative_sha256": sha(HERE / copies[1][1]),
                        "saved_processing_sha256": sha(HERE / copies[2][1])})
    report = {"case_id": entry["case_id"], "primary_construction_sha256": entry["construction_sha256"],
              "fallbacks": reports, "exact_cpu_paths_passed": True,
              "physical_acceptance_claimed": False}
    (HERE / (name + "-fallback-proof.json")).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_id": entry["case_id"], "fallbacks": len(reports),
                      "exact_cpu_paths_passed": True, "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    main(args.name)
