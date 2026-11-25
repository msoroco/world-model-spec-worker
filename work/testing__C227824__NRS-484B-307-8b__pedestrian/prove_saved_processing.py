"""Run recorded-only positive and missing-source diagnostic processing for six cases."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from build_construction import ROOT


REPO = ROOT.parents[1]
PRIVATE = REPO / ".runtime-work" / "c227824-saved-processing-v1"
VALIDATOR = REPO / ".runtime-work" / "c229439-validator" / ".lake" / "build" / "bin" / "adapterCheck"


def command(*args):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["TMPDIR"] = str(PRIVATE)
    run = subprocess.run([sys.executable, str(REPO / "runtime.py"), *map(str, args)],
                         cwd=REPO, env=env, capture_output=True, text=True, timeout=600)
    if run.returncode:
        raise RuntimeError(" ".join(map(str, args[:2])) + ": " + run.stdout[-1000:] + run.stderr[-2500:])
    return json.loads(run.stdout)


def main():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    manifest = ROOT / "execution-manifest.draft.json"
    entries = json.loads(manifest.read_text())["cases"]
    rows = []
    for entry in entries:
        case_id = entry["case_id"]
        suffix = case_id[len(ROOT.name) + 2:]
        root = PRIVATE / suffix
        if root.exists():
            shutil.rmtree(root)
        root.mkdir()
        attempt = root / "attempt"
        fixture = root / "fixture"
        output = root / "positive-versions"
        command("materialize", "--manifest", manifest, "--case", case_id,
                "--output", attempt)
        command("fixture", "--recipe", REPO / entry["fixture_recipe"],
                "--output", fixture)
        for source in fixture.iterdir():
            target = attempt / source.name
            if target.exists():
                raise ValueError("synthetic fixture shadows package")
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copyfile(source, target)
        positive = command("process-saved", "--manifest", manifest, "--case", case_id,
                           "--attempt", attempt, "--output", output,
                           "--library", REPO / "runtime" / "library",
                           "--validator", VALIDATOR)
        if (positive.get("passed") is not True or positive.get("missing_evidence") is not False
                or positive.get("physical_acceptance_claimed") is not False
                or positive.get("final_video_checks") is None):
            raise ValueError("recorded-only positive diagnostic processing incomplete")
        negative = root / "negative-attempt"
        shutil.copytree(attempt, negative)
        (negative / "device-history.jsonl").unlink()
        missing = command("process-saved", "--manifest", manifest, "--case", case_id,
                          "--attempt", negative, "--output", root / "negative-versions",
                          "--library", REPO / "runtime" / "library",
                          "--validator", VALIDATOR)
        if missing.get("missing_evidence") is not True or missing.get("physical_acceptance_claimed") is not False:
            raise ValueError("recorded-only missing source did not produce feedback")
        rows.append({"case_id": case_id, "positive_passed": True,
                     "positive_final_decoded": True, "negative_missing_evidence": True,
                     "recorded_only": True, "diagnostic_fixture_only": True})
    print(json.dumps({"format": "c227824-synthetic-saved-processing-summary",
                      "cases": rows, "physical_acceptance_claimed": False}, indent=2))


if __name__ == "__main__":
    main()
