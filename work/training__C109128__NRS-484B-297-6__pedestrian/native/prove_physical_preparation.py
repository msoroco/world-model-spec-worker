"""Exercise geometric completion and lifecycle on declared synthetic fixtures."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parents[1]
SCRATCH = REPO / ".runtime-work/c109128/physical-fixtures"
SOURCES = ("config.json", "sidewalk_context.json", "pedestrian-original.jsonl",
           "video_frames.jsonl", "camera-sources.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def main():
    from physical_completion import validate_lifecycle
    manifest = read(FOLDER / "execution-manifest.json")
    results = []
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        source = (REPO / ".runtime-work/c109128/selected-compat-refresh" / (suffix + "-primary")
                  if suffix.startswith("condition_") else
                  REPO / ".runtime-work/c109128/alt-compat-current" / (suffix + "-primary"))
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            attempt = SCRATCH / suffix / kind
            attempt.mkdir(parents=True, exist_ok=True)
            for name in SOURCES:
                target = attempt / name
                if target.exists():
                    target.unlink()
                shutil.copy2(source / name, target)
            if kind == "incomplete_motion":
                path = attempt / "pedestrian-original.jsonl"
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                for row in rows[300:]:
                    row["footprint_xy_m"] = [[x, -3.1 + (i % 2) * .2]
                                             for i, (x, _) in enumerate(row["footprint_xy_m"])]
                path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            if kind == "missing_evidence":
                (attempt / "sidewalk_context.json").unlink()
            result = FOLDER / f"physical-{suffix}-{kind}-result.json"
            log = FOLDER / f"physical-{suffix}-{kind}.log"
            command = [sys.executable, str(FOLDER / "physical_completion.py"),
                       "--attempt", str(attempt), "--output", str(result)]
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            with log.open("w") as stream:
                completed = subprocess.run(command, cwd=REPO, env=env,
                                           stdout=stream, stderr=subprocess.STDOUT)
            if completed.returncode:
                raise ValueError("Physical fixture checker failed: " + suffix + " " + kind)
            expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                        "missing_evidence": "unverified"}[kind]
            if read(result)["physical_checks"]["maneuver"]["status"] != expected:
                raise ValueError("Physical fixture status differs: " + suffix + " " + kind)
            fixtures.append({"kind": kind, "command": " ".join(command),
                             "exit_code": 0, "log": log.name, "log_sha256": sha(log),
                             "result": result.name, "result_sha256": sha(result)})
        lifecycle = ["capture_finished", "encoders_closed", "restoration_verified",
                     "native_exit", "owner_released", "saved_processing_started"]
        validate_lifecycle(lifecycle)
        try:
            validate_lifecycle(lifecycle[:4] + lifecycle[5:])
        except ValueError as error:
            negative = str(error)
        else:
            raise AssertionError("Missing owner-release negative accepted")
        log = FOLDER / f"physical-{suffix}-lifecycle.log"
        log.write_text("positive lifecycle order passed\nnegative rejected: " + negative + "\n")
        proof = {"format": "c109128-physical-preparation-cpu-proof-v1",
                 "case_id": entry["case_id"],
                 "construction_sha256": entry["construction_sha256"],
                 "fixtures": fixtures,
                 "lifecycle": {"events": lifecycle, "exit_code": 0,
                               "log": log.name, "log_sha256": sha(log)},
                 "original_native_executed": False}
        receipt = FOLDER / f"physical-{suffix}-preparation.json"
        write(receipt, proof)
        entry["physical_preparation"] = {"receipt": receipt.name, "sha256": sha(receipt)}
        results.append({"case_id": entry["case_id"], "receipt": receipt.name,
                        "sha256": sha(receipt)})
    write(FOLDER / "execution-manifest.json", manifest)
    print(json.dumps({"cases": len(results), "results": results}))


if __name__ == "__main__":
    sys.path.insert(0, str(FOLDER))
    main()
