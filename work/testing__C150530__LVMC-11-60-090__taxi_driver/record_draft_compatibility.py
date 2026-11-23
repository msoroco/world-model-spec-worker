"""Retain exact synthetic compatibility receipts without claiming delivery readiness."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
RUNS = {"near_stand": "c150530-compat-near-v7",
        "far_stand": "c150530-compat-far-v1",
        "near_stand_straight": "c150530-compat-straight-v1"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    proofs = []
    manifest = ROOT / "execution-manifest.draft.json"
    for case, run in RUNS.items():
        source = REPO / ".runtime-work" / run
        folder = ROOT / "cases" / case
        copied = {}
        for original, retained in (
                ("compatibility.json", "primary-compatibility.json"),
                ("compatibility-analysis.log", "primary-compat-analysis.log"),
                ("negative-analysis.log", "primary-compat-negative.log")):
            target = folder / retained
            shutil.copyfile(source / original, target)
            copied[original] = {"path": target.relative_to(ROOT).as_posix(),
                                "sha256": sha(target)}
        command_log = REPO / ".runtime-work" / (run + "-command.log")
        if not (json.loads((source / "compatibility.json").read_text()).get("passed") is True
                and '"negative_removed": "reviewed-context.json"' in command_log.read_text()):
            raise ValueError("Pinned compatibility proof did not pass exact negative")
        target = folder / "primary-compat-command.log"
        shutil.copyfile(command_log, target)
        proofs.append({"case_id": ASSIGNMENT + "__" + case,
                       "construction_sha256": next(entry["construction_sha256"]
                                                  for entry in json.loads(manifest.read_text())["cases"]
                                                  if entry["case_id"] == ASSIGNMENT + "__" + case),
                       "command": "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py compatibility --manifest work/" + ASSIGNMENT + "/execution-manifest.draft.json --case " + ASSIGNMENT + "__" + case + " --output .runtime-work/" + run + " --library runtime/library --validator .runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck",
                       "exit_code": 0, "receipt": copied["compatibility.json"],
                       "analysis_log": copied["compatibility-analysis.log"],
                       "negative_log": copied["negative-analysis.log"],
                       "command_log": {"path": target.relative_to(ROOT).as_posix(),
                                       "sha256": sha(target)},
                       "scope": "synthetic software compatibility only"})
    report = {"format": "c150530-draft-compatibility-proofs-v1",
              "assignment_id": ASSIGNMENT, "cases": proofs,
              "delivery_ready": False,
              "limitation": "Original documentary review, saved-only lifecycle, pixel acceptance and local integration remain open"}
    (ROOT / "pinned-compatibility-proofs.draft.json").write_text(
        json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
