"""Independent source and frame audit for saved right-curb Native attempts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from curb_geometry import ASSIGNMENT, measure_original
from native_acquisition import CAMERAS


def _read(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("original source missing: " + path.name)
    return json.loads(path.read_text())


def audit(attempt, case_id, *, require_native_attestation=False):
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("wrong exact right-curb case")
    root = Path(attempt) / "original-attempt"
    inventory = _read(root / "inventory.json")
    diagnostic = inventory.get("diagnostic_fixture") is True
    count = inventory.get("frame_count")
    if count not in ((9, 900) if diagnostic else (900,)):
        raise ValueError("original right-curb diagnostic frame count differs")
    if require_native_attestation and diagnostic:
        raise ValueError("diagnostic fixture cannot attest physical Native capture")
    if (inventory.get("case_id") != case_id or inventory.get("source_kind") != "original_native" or
            inventory.get("frame_count") != count or inventory.get("rate_hz") != 20 or
            inventory.get("physical_completion") is not False):
        raise ValueError("original right-curb inventory differs")
    sources = inventory.get("source_sha256")
    expected = {"site.json", "plan.json", "actors.json", "road.xodr", "wheel-motion.jsonl",
                "wheel-seal.json", "frame-map.json", "measurement.json"}
    if not isinstance(sources, dict) or set(sources) != expected:
        raise ValueError("original right-curb source inventory incomplete")
    for name, digest in sources.items():
        path = root / name
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("original right-curb source hash differs: " + name)
    site = _read(root / "site.json")
    plan = _read(root / "plan.json")
    actors = _read(root / "actors.json")
    if (site.get("case_id") != case_id or plan.get("case_id") != case_id or
            not actors.get("ego_vehicle_id") or not actors.get("actual_blueprint")):
        raise ValueError("original right-curb site, plan or actor identity differs")
    if sources["road.xodr"] != site["sources"]["native_opendrive_map"]["sha256"]:
        raise ValueError("original Native map differs from reviewed map")
    mapping = _read(root / "frame-map.json")
    if mapping.get("case_id") != case_id or len(mapping.get("frames", [])) != count:
        raise ValueError("original right-curb frame map incomplete")
    for index, frame in enumerate(mapping["frames"]):
        if frame.get("frame") != index or (index and
                (frame.get("native_frame") != mapping["frames"][index - 1]["native_frame"] + 1 or
                 abs(frame.get("native_time_s") - mapping["frames"][index - 1]["native_time_s"] - .05) > .001)):
            raise ValueError("original right-curb frame map gap")
    diagnostic_ledgers = inventory.get("diagnostic_camera_ledgers_sha256")
    if diagnostic and diagnostic_ledgers is not None:
        if not isinstance(diagnostic_ledgers, dict) or set(diagnostic_ledgers) != set(CAMERAS):
            raise ValueError("four diagnostic camera ledgers missing")
        for name in CAMERAS:
            path = root / (name + ".frames.json")
            if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != diagnostic_ledgers[name]:
                raise ValueError("diagnostic camera ledger source hash differs: " + name)
            rows = _read(path)
            if not isinstance(rows, list) or len(rows) != count:
                raise ValueError("diagnostic camera ledger incomplete: " + name)
            for index, row in enumerate(rows):
                if (row.get("frame") != index or
                        row.get("native_frame") != mapping["frames"][index]["native_frame"] or
                        not isinstance(row.get("png_sha256"), str) or len(row["png_sha256"]) != 64):
                    raise ValueError("diagnostic camera ledger frame differs: " + name)
    else:
        cameras = inventory.get("camera_sha256")
        if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
            raise ValueError("four original camera hashes missing")
        for name in CAMERAS:
            archive_path = root / (name + ".zip")
            if archive_path.is_symlink() or not archive_path.is_file() or \
                    hashlib.sha256(archive_path.read_bytes()).hexdigest() != cameras[name]:
                raise ValueError("original camera source hash differs: " + name)
            with zipfile.ZipFile(archive_path) as archive:
                entries = archive.namelist()
                if len(entries) != count or len(set(entries)) != count:
                    raise ValueError("original camera frames incomplete: " + name)
                for index, entry in enumerate(entries):
                    native_frame = mapping["frames"][index]["native_frame"]
                    if entry != f"{index:04d}-{native_frame}.png" or not archive.read(entry).startswith(b"\x89PNG\r\n\x1a\n"):
                        raise ValueError("original camera frame invalid: " + name)
    measurement = measure_original(attempt, case_id, diagnostic=diagnostic)
    if measurement != _read(root / "measurement.json"):
        raise ValueError("saved right-curb measurement differs")
    return {"case_id": case_id, "structural_status": "passed",
            "frame_count": count, "camera_count": len(CAMERAS),
            "diagnostic_fixture": diagnostic, "physical_completion": False,
            "legal_judgment": "unresolved", "measurement": measurement}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-native-attestation", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to replace independent original audit")
    result = audit(args.attempt, args.case_id,
                   require_native_attestation=args.require_native_attestation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
