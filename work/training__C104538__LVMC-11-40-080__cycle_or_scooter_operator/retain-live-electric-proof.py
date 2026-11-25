"""Retain exact selected-manifest electric CPU replay receipts."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
LIVE = REPO / ".runtime-work/c104538-electric-live"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def retain(source: Path, dest: Path) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    return {"path": str(dest.relative_to(ROOT)), "sha256": sha(dest)}


def main() -> None:
    manifest_path = ROOT / "execution-manifest.json"
    manifest_sha = sha(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    rows = []
    for entry in manifest["cases"]:
        label = entry["case_id"].split("__")[-1]
        if not label.startswith("electric_"):
            continue
        row = {"case_id": entry["case_id"], "candidates": {}}
        for candidate in ("primary", "fallback1"):
            attempt = LIVE / ("compat-" + label +
                              ("-fallback1" if candidate == "fallback1" else ""))
            selection = json.loads((attempt / "candidate-selection.json").read_text())
            receipt = json.loads((attempt / "compatibility.json").read_text())
            expected_sha = (entry["construction_sha256"] if candidate == "primary"
                            else entry["candidates"][0]["construction_sha256"])
            if (selection["manifest_sha256"] != manifest_sha or
                    selection["candidate_id"] != candidate or
                    selection["construction_sha256"] != expected_sha or
                    receipt["passed"] is not True or
                    receipt["construction_sha256"] != expected_sha):
                raise ValueError("Live candidate proof differs from selected manifest: " + label)
            destination = ROOT / "electric-drafts" / label / "live-proof" / candidate
            row["candidates"][candidate] = {
                name: retain(attempt / source, destination / target)
                for name, source, target in (("selection", "candidate-selection.json", "candidate-selection.json"),
                                             ("compatibility", "compatibility.json", "compatibility.json"),
                                             ("analysis_log", "compatibility-analysis.log", "analysis.log"),
                                             ("negative_log", "negative-analysis.log", "negative.log"))}
        saved = LIVE / ("saved-" + label) / "v0001/processing.json"
        processing = json.loads(saved.read_text())
        if (processing["passed"] is not True or
                processing["recorded_only"] is not True or
                processing["physical_acceptance_claimed"] is not False or
                processing["legal_acceptance_claimed"] is not False):
            raise ValueError("Saved-only electric replay did not pass: " + label)
        row["saved_processing"] = retain(
            saved, ROOT / "electric-drafts" / label / "live-proof/saved-processing.json")
        rows.append(row)
    result = {"format": "c104538-exact-selected-electric-cpu-proof-v1",
              "manifest_sha256": manifest_sha, "case_count": len(rows),
              "candidate_count": sum(len(row["candidates"]) for row in rows),
              "recorded_only": True, "physical_acceptance_claimed": False,
              "legal_acceptance_claimed": False, "cases": rows}
    output = ROOT / "electric-drafts/live-selected-proof-index.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"manifest_sha256": manifest_sha, "case_count": len(rows),
                      "candidate_count": result["candidate_count"],
                      "index_sha256": sha(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
