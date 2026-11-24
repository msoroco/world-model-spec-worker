"""Bind officer diagnostic physical-classifier and owner-lifecycle fixtures."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PREFIX = HERE.relative_to(REPO)
MANIFEST = HERE / "officer-pair-current-draft-manifest.json"
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main():
    output_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    assert REPO / ".runtime-work" in output_root.parents
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        name = "officer-controlled" if suffix == "officer_controls_ego" else "officer-not-controlled"
        source = REPO / ".runtime-work" / (
            "c158196-" + name + "-compatibility-" +
            ("second" if name == "officer-controlled" else "first"))
        saved = HERE / (name + "-current-process-saved.json")
        folder = HERE / "physical-proofs" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        receipt = {"format": "worker-physical-preparation-fixtures", "case_id": case,
                   "construction_sha256": entry["construction_sha256"],
                   "diagnostic_fixture": True, "physical_acceptance_claimed": False,
                   "saved_processing_sha256": sha(saved), "fixtures": []}
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence", "lifecycle"):
            output = folder / (kind + ".json")
            log = folder / (kind + ".log")
            command = [".venv-cpu/bin/python", str(PREFIX / "physical_fixture_proof.py"),
                       "--manifest", str(MANIFEST.relative_to(REPO)), "--case", case,
                       "--source", str(source.relative_to(REPO)), "--kind", kind,
                       "--output", str(output.relative_to(REPO)),
                       "--saved-receipt", str(saved.relative_to(REPO))]
            result = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
            log.write_text(result.stdout + result.stderr)
            if result.returncode:
                raise RuntimeError(suffix + "/" + kind + " failed: " + log.read_text())
            item = {"kind": kind, "command": " ".join(command), "exit_code": 0,
                    "log": str(log.relative_to(HERE)), "log_sha256": sha(log),
                    "result": str(output.relative_to(HERE)), "result_sha256": sha(output)}
            if kind == "lifecycle":
                item["events"] = json.loads(output.read_text())["events"]
                assert item["events"] == EVENTS
                receipt["lifecycle"] = item
            else:
                receipt["fixtures"].append(item)
        receipt_path = folder / "receipt.json"
        write(receipt_path, receipt)
        entry["physical_preparation"] = {"receipt": str(receipt_path.relative_to(HERE)),
                                          "sha256": sha(receipt_path)}
        print(suffix + ": physical classifier and lifecycle fixtures passed")
    write(MANIFEST, manifest)


if __name__ == "__main__":
    main()
