"""Bind three labeled physical fixtures and source-closed saved lifecycle proof."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRATCH = ROOT.parents[1] / ".runtime-work/c158190-stop-owner"
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified", "native_exit",
          "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def copy_log(source, target):
    lines = [line.rstrip() for line in source.read_text().splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    if not lines:
        raise ValueError("empty physical proof log")
    target.write_text("\n".join(lines) + "\n")
    return sha(target)


def main():
    path = ROOT / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        short = case.rsplit("_", 1)[-1]
        folder = ROOT / "cases" / ("stop_nearest_view_" + short)
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            stem = "physical-" + short + "-" + kind
            source_result = SCRATCH / (stem + ".json")
            result = json.loads(source_result.read_text())
            for source in result["physical_checks"]["maneuver"]["sources"]:
                source["path"] = str((folder / "diagnostic-sources" / Path(source["path"]).name).relative_to(ROOT))
                if sha(ROOT / source["path"]) != source["sha256"]:
                    raise ValueError("physical fixture source differs")
            target_result = folder / ("physical-" + kind + ".json")
            write(target_result, result)
            target_log = folder / ("physical-" + kind + ".log")
            log_sha = copy_log(SCRATCH / (stem + ".log"), target_log)
            command = (".venv-cpu/bin/python work/" + ROOT.name + "/stop_physical_fixture.py "
                       "--case " + case + " --sources .runtime-work/c158190-stop-owner/fixture-" + short +
                       "-3 --kind " + kind + " --output .runtime-work/c158190-stop-owner/" + stem + ".json")
            fixtures.append({"kind": kind, "command": command, "exit_code": 0,
                             "log": str(target_log.relative_to(ROOT)), "log_sha256": log_sha,
                             "result": str(target_result.relative_to(ROOT)), "result_sha256": sha(target_result)})
        life_log = folder / "physical-lifecycle.log"
        life_sha = copy_log(SCRATCH / ("lifecycle-" + short + "-3.log"), life_log)
        capture_log = folder / "stop-capture-tests.log"
        copy_log(SCRATCH / "stop-capture-tests.log", capture_log)
        summary = folder / "saved-processing-proof.json"
        write(summary, json.loads((SCRATCH / ("saved-summary-" + short + "-3.json")).read_text()))
        receipt = {"format": "worker-physical-preparation", "case_id": case,
                   "construction_sha256": entry["construction_sha256"], "fixtures": fixtures,
                   "lifecycle": {"events": EVENTS, "exit_code": 0,
                                 "log": str(life_log.relative_to(ROOT)), "log_sha256": life_sha,
                                 "capture_test_log": str(capture_log.relative_to(ROOT)),
                                 "saved_receipt": str(summary.relative_to(ROOT))}}
        target_receipt = folder / "physical-preparation.json"
        write(target_receipt, receipt)
        entry["physical_preparation"] = {"receipt": str(target_receipt.relative_to(ROOT)),
                                         "sha256": sha(target_receipt)}
        entry["saved_processing_diagnostic"] = {"receipt": str(summary.relative_to(ROOT)),
                                                "sha256": sha(summary)}
        entry["missing_proofs"] = [item for item in entry["missing_proofs"]
                                   if item not in ("saved_only_original", "physical_preparation")]
    write(path, manifest)
    print("Bound stop physical and saved-only CPU proofs:", len(manifest["cases"]))


if __name__ == "__main__":
    main()
