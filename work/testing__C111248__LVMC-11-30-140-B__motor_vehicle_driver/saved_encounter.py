"""Saved-only, source-hashed blind-person encounter measurements.

This code reads an already closed original history. It never drives a simulator
or decides what the statute requires in a particular circumstance.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ASSIGNMENT_ID = HERE.name
spec = importlib.util.spec_from_file_location("blind_encounter", HERE / "blind_encounter.py")
encounter = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = encounter
spec.loader.exec_module(encounter)
audit_spec = importlib.util.spec_from_file_location("blind_delivery_audit", HERE / "delivery_audit.py")
delivery_audit = importlib.util.module_from_spec(audit_spec)
audit_spec.loader.exec_module(delivery_audit)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_bound_source(root: Path, entry: dict, *, kind: str):
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
        raise ValueError(f"missing {kind} source path")
    path = (root / entry["path"]).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"missing or escaping {kind} source")
    expected = entry.get("sha256")
    if not isinstance(expected, str) or len(expected) != 64 or sha256(path) != expected:
        raise ValueError(f"{kind} source hash mismatch")
    return path, expected


def process(manifest_path: Path, output_path: Path) -> dict:
    manifest_path = manifest_path.resolve()
    output_path = Path(output_path)
    if output_path.exists() or output_path.is_symlink():
        raise ValueError("preserve prior saved encounter output; choose a fresh path")
    spec = json.loads(manifest_path.read_text(encoding="utf-8"))
    if spec.get("assignment_id") != ASSIGNMENT_ID:
        raise ValueError("assignment identity mismatch")
    case_id = spec.get("case_id")
    if case_id not in encounter.CASE_BY_ID:
        raise ValueError("exact case identity mismatch")
    root = manifest_path.parent
    history_path, history_hash = read_bound_source(root, spec.get("original_history"), kind="original history")
    att_path, att_hash = read_bound_source(root, spec.get("blindness_attestation"), kind="blindness attestation")
    cue_path, cue_hash = read_bound_source(root, spec.get("carried_cue"), kind="carried cue")
    if len({history_path, att_path, cue_path}) != 3:
        raise ValueError("independent sources must be distinct files")
    att = json.loads(att_path.read_text(encoding="utf-8"))
    cue = json.loads(cue_path.read_text(encoding="utf-8"))
    if not att.get("source_sha256") or not cue.get("source_sha256"):
        raise ValueError("attestation or cue provenance missing")
    if att.get("basis") not in ("wholly_blind", "partially_blind") or not att.get("issuer"):
        raise ValueError("independent blindness basis and issuer required")
    if cue.get("observation") != "actually_carried" or not cue.get("observer_source"):
        raise ValueError("observed carried cue source required")
    rows = [json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines() if line]
    if spec.get("original_frame_count") != len(rows):
        raise ValueError("original frame count mismatch")
    measurement = encounter.measure_saved(case_id, rows, attestation=att, cue_source=cue)
    measurement["source_bindings"] = {
        "original_history": history_hash,
        "blindness_attestation": att_hash,
        "carried_cue": cue_hash,
        "saved_manifest": sha256(manifest_path),
    }
    if spec.get("original_media_map") is not None:
        measurement["original_media_audit"] = delivery_audit.audit(manifest_path)
    measurement["physical_acceptance_claimed"] = False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(measurement, indent=2, sort_keys=True) + "\n")
    return measurement


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    process(args.manifest, args.output)


if __name__ == "__main__":
    main()
