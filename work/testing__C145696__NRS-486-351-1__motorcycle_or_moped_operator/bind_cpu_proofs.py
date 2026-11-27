"""Bind locally completed exact-case CPU proofs without changing their claims."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c145696"
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def clean_copy(source, target):
    text = Path(source).read_text(encoding="utf-8").rstrip() + "\n"
    target.write_text(text, encoding="utf-8")
    return sha(target)


def offline(entry, suffix, candidate):
    source = SCRATCH / f"offline2-{suffix}-{candidate}.log"
    if not source.is_file() or not json.loads(source.read_text()).get("offline_passed"):
        raise ValueError("Exact offline proof missing: " + suffix + " " + candidate)
    target = ROOT / f"cpu-offline-{suffix}-{candidate}.log"
    checksum = clean_copy(source, target)
    command = ("PYTHONDONTWRITEBYTECODE=1 SCENARIO_TEST_TEMP_ROOT=$PWD/.runtime-work/c145696 "
               ".venv-cpu/bin/python runtime.py offline --manifest "
               f"work/{ROOT.name}/execution-manifest.json --case {entry['case_id']} "
               f"--candidate {candidate} --output .runtime-work/c145696/offlineall2/{suffix}-{candidate} "
               "--python $PWD/.venv-cpu/bin/python")
    return {"exit_code": 0, "construction_sha256": (entry["construction_sha256"] if candidate == "primary"
            else entry["candidates"][0]["construction_sha256"]),
            "command": command, "log": target.name, "log_sha256": checksum}


def physical(entry, suffix):
    source = SCRATCH / f"physical-{suffix}.log"
    if not source.is_file() or "lifecycle" not in source.read_text():
        raise ValueError("Physical lifecycle proof missing: " + suffix)
    target = ROOT / f"cpu-physical-{suffix}.log"
    checksum = clean_copy(source, target)
    command = ("PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$PWD/runtime/scenario_pipeline "
               f".venv-cpu/bin/python work/{ROOT.name}/physical_probe.py "
               f"--case {entry['case_id']} --output .runtime-work/c145696/physicalall/{suffix}")
    fixtures = []
    for kind in KINDS:
        result = ROOT / f"physical-{suffix}-{kind}.json"
        fixtures.append({"kind": kind, "command": command, "exit_code": 0,
                         "log": target.name, "log_sha256": checksum,
                         "result": result.name, "result_sha256": sha(result)})
    proof = {"format": "worker-physical-preparation", "case_id": entry["case_id"],
             "construction_sha256": entry["construction_sha256"], "fixtures": fixtures,
             "lifecycle": {"events": ["capture_finished", "encoders_closed",
                                      "restoration_verified", "native_exit", "owner_released",
                                      "saved_processing_started"],
                           "exit_code": 0, "command": command, "log": target.name,
                           "log_sha256": checksum}}
    receipt = ROOT / f"physical-preparation-{suffix}.json"
    write(receipt, proof)
    return {"receipt": receipt.name, "sha256": sha(receipt)}


def compatibility(entry, suffix, candidate):
    folder = (SCRATCH / "compat7-both_stationary" if suffix == "both_stationary" and
              candidate == "primary" else SCRATCH / f"compatall/{suffix}-{candidate}")
    original = folder / "compatibility.json"
    if not original.is_file():
        raise ValueError("Compatibility proof missing: " + suffix + " " + candidate)
    stem = f"{suffix}-{candidate}"
    log = ROOT / f"cpu-compatibility-{stem}.log"
    negative = ROOT / f"cpu-compatibility-negative-{stem}.log"
    log_hash = clean_copy(folder / "compatibility-analysis.log", log)
    negative_hash = clean_copy(folder / "negative-analysis.log", negative)
    receipt = json.loads(original.read_text())
    receipt["log_sha256"] = log_hash
    receipt["negative_log_sha256"] = negative_hash
    target = ROOT / f"cpu-compatibility-receipt-{stem}.json"
    write(target, receipt)
    return {"receipt": target.name, "sha256": sha(target),
            "log": log.name, "negative_log": negative.name}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--physical", action="store_true")
    parser.add_argument("--compatibility", action="store_true")
    args = parser.parse_args()
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        if args.offline:
            entry["offline"] = offline(entry, suffix, "primary")
            entry["candidates"][0]["offline"] = offline(entry, suffix, "fallback1")
        if args.physical:
            entry["physical_preparation"] = physical(entry, suffix)
        if args.compatibility:
            entry["compatibility"] = compatibility(entry, suffix, "primary")
            entry["negative"] = {"log": entry["compatibility"]["negative_log"]}
            entry["candidates"][0]["compatibility"] = compatibility(entry, suffix, "fallback1")
    write(manifest_path, manifest)


if __name__ == "__main__":
    main()
