"""Run saved-source diagnostics for electric candidate constructions.

Uses the existing bicycle synthetic motion and camera fixture only as a software
test of class-specific joins. It never represents an electric Native capture.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c104538-electric"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    rows = []
    negatives = []
    for machine in ("electric_bicycle", "electric_scooter"):
        for behavior, source_case in (("obey", "controlled_1"),
                                      ("turn", "controlled_2"),
                                      ("dismount", "controlled_3")):
            label = f"{machine}_{behavior}"
            source = REPO / ".runtime-work/c104538-rebind" / f"compat-{source_case}-primary"
            materialized = SCRATCH / label
            dest = SCRATCH / ("saved-" + label)
            if dest.exists():
                shutil.rmtree(dest)
            dest.mkdir(parents=True)
            for relative in ("authored-sign.json", "native_samples.jsonl",
                             "video_frames.jsonl", "trace.jsonl", "body_history.jsonl",
                             "capture/evidence.jsonl", "capture/manifest.json",
                             "overview.mkv", "approach.mkv", "reference_corner.mkv",
                             "driver_reference.mkv"):
                target = dest / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                os.link(source / relative, target)
            shutil.copy2(materialized / "config.json", dest / "config.json")
            rider = [json.loads(line) for line in (source / "rider_native_samples.jsonl").read_text().splitlines()]
            for row in rider:
                row["machine_class"] = machine
            (dest / "rider_native_samples.jsonl").write_text(
                "".join(json.dumps(row, allow_nan=False) + "\n" for row in rider))
            manifest = json.loads((source / "rider-source-manifest.json").read_text())
            manifest["rider_samples_sha256"] = sha(dest / "rider_native_samples.jsonl")
            (dest / "rider-source-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
            output = dest / "electric-diagnostic.json"
            command = ["python3.11", str(materialized / "finalize.py"),
                       "--attempt", str(dest), "--output", str(output)]
            run = subprocess.run(command, capture_output=True, text=True,
                                 env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
                                      "PYTHONPATH": str(REPO / "runtime/scenario_pipeline") + os.pathsep +
                                                    str(REPO / "runtime/python")})
            if run.returncode:
                raise RuntimeError(label + ": " + run.stderr[-2000:])
            report = json.loads(output.read_text())
            if (report.get("original_native_capture_executed") is not False or
                    report.get("legal_verdict_claimed") is not False):
                raise ValueError("Electric diagnostic claimed original or legal proof")
            rows.append({"case": label, "construction_sha256": sha(
                ROOT / "electric-drafts" / label / "construction.json"),
                         "offline_log_sha256": sha(materialized / "offline.log"),
                         "saved_report_sha256": sha(output),
                         "original_native_capture_executed": False,
                         "electric_asset_observed": False,
                         "synthetic_class_join_passed": True})
            if behavior == "obey":
                bad = SCRATCH / ("saved-negative-" + label)
                if bad.exists():
                    shutil.rmtree(bad)
                shutil.copytree(dest, bad, copy_function=os.link)
                for relative in ("result.json", "electric-diagnostic.json"):
                    (bad / relative).unlink()
                shutil.rmtree(bad / "channels")
                bad_rider = bad / "rider_native_samples.jsonl"
                altered = bad_rider.read_text().splitlines()
                first = json.loads(altered[0])
                first["machine_class"] = "bicycle"
                altered[0] = json.dumps(first, allow_nan=False)
                bad_rider.unlink()
                bad_rider.write_text("\n".join(altered) + "\n")
                bad_manifest = bad / "rider-source-manifest.json"
                contents = json.loads(bad_manifest.read_text())
                contents["rider_samples_sha256"] = sha(bad_rider)
                bad_manifest.unlink()
                bad_manifest.write_text(json.dumps(contents, indent=2) + "\n")
                bad_run = subprocess.run(["python3.11", str(materialized / "finalize.py"),
                                          "--attempt", str(bad),
                                          "--output", str(bad / "negative-report.json")],
                                         capture_output=True, text=True,
                                         env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
                                              "PYTHONPATH": str(REPO / "runtime/scenario_pipeline") +
                                                            os.pathsep + str(REPO / "runtime/python")})
                if bad_run.returncode == 0 or "Rider/sign/frame source join differs" not in bad_run.stderr:
                    raise ValueError("Electric class-tamper diagnostic was not rejected")
                negatives.append({"case": label, "wrong_machine_class_rejected": True})
    report = {"format": "c104538-electric-candidate-cpu-diagnostics-v1",
              "cases": rows, "negative_source_checks": negatives,
              "scope": "synthetic machine-class join and finalizer software test",
              "reviewed_native_asset_observed": False,
              "physical_or_legal_acceptance_claimed": False}
    (ROOT / "electric-drafts/proof-index.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
