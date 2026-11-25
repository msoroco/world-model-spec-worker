"""Audit a sealed C111301 Native attempt after its owner has been released.

This verifies source identity, the saved participant measurement, complete
four-camera decoding and a finite reverse-motion milestone. It does not infer
participant visibility or a legal right-of-way verdict from pixels.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "runtime"))
from media_decode import audit_media
from saved_backing import CAMERAS
from scenario_pipeline.worker_exchange.native_output import physical_result

ASSIGNMENT = HERE.name
SUFFIXES = ("pedestrian_yield", "pedestrian_continue", "traffic_yield", "traffic_continue")
REQUIRED_SOURCES = {"acquisition.json", "acquisition-provenance.json", "map.json", "road.xodr",
                    "telemetry.json", "frame-map.json", "trace.jsonl", "video_frames.jsonl",
                    "config.json", "construction.json", "runner.py"} | {name + ".mkv" for name in CAMERAS}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def confined(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("sealed source path escapes attempt")
    root = Path(root).resolve()
    raw = root / relative
    if any(path.is_symlink() for path in (raw, *raw.parents) if path != root and root in path.parents):
        raise ValueError("sealed source uses a linked path")
    path = raw.resolve()
    if root not in path.parents or not path.is_file():
        raise ValueError("sealed source missing: " + relative)
    return path


def verify_seal(attempt, *, diagnostic_test=False, owner_release_receipt=None):
    root = Path(attempt).resolve()
    provenance = json.loads((root / "acquisition-provenance.json").read_text())
    expected = "synthetic_fixture" if diagnostic_test else "native"
    if provenance.get("provenance_kind") != expected or provenance.get("diagnostic_fixture") is not diagnostic_test:
        raise ValueError("original Native provenance required" if not diagnostic_test else "diagnostic fixture provenance required")
    seal_path = root / "capture-seal.json"
    seal = json.loads(seal_path.read_text())
    if seal.get("format") != "worker-sealed-capture" or seal.get("diagnostic_fixture") is not diagnostic_test:
        raise ValueError("sealed capture provenance differs")
    if seal.get("frames") != 900 or seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"]:
        raise ValueError("incomplete capture lifecycle")
    if seal.get("restoration", {}).get("restored") is not True or any(code != 0 for code in seal.get("encoder_exit_codes", {}).values()):
        raise ValueError("Native restoration or video closure failed")
    revision = seal.get("native_revision", {})
    if revision.get("construction_sha256") != sha(root / "construction.json") or revision.get("runner_sha256") != sha(root / "runner.py"):
        raise ValueError("Native revision differs from capture seal")
    sources = seal.get("sources")
    if not isinstance(sources, dict) or not REQUIRED_SOURCES <= set(sources):
        raise ValueError("sealed original source inventory missing")
    source_digest = hashlib.sha256(json.dumps(sources, sort_keys=True, separators=(",", ":"),
                                               ensure_ascii=False).encode()).hexdigest()
    if seal.get("source_digest") != source_digest:
        raise ValueError("capture source inventory digest differs")
    for name, expected_sha in sources.items():
        if sha(confined(root, name)) != expected_sha:
            raise ValueError("sealed original source changed: " + name)
    if not diagnostic_test:
        exit_path = root / "native-exit.json"
        exited = json.loads(exit_path.read_text())
        if exited.get("event") != "native_exit" or exited.get("capture_seal_sha256") != sha(seal_path) or exited.get("native_revision") != revision:
            raise ValueError("Native exit does not bind the sealed capture")
        if not owner_release_receipt:
            raise ValueError("operator owner-release receipt required")
        owner = json.loads(Path(owner_release_receipt).read_text())
        if (owner.get("event") != "owner_released" or owner.get("operator_attested") is not True or
                owner.get("native_construction_sha256") != revision["construction_sha256"] or
                owner.get("native_exit_sha256") != sha(exit_path)):
            raise ValueError("operator owner release differs from Native exit")
    return seal


def audit(attempt, case_id, *, diagnostic_test=False, owner_release_receipt=None):
    root = Path(attempt).resolve()
    if case_id not in {ASSIGNMENT + "__" + suffix for suffix in SUFFIXES}:
        raise ValueError("another exact C111301 case selected")
    seal = verify_seal(root, diagnostic_test=diagnostic_test, owner_release_receipt=owner_release_receipt)
    receipt = json.loads((root / "acquisition.json").read_text())
    if receipt.get("case_id") != case_id or receipt.get("assignment_id") != ASSIGNMENT:
        raise ValueError("acquisition exact case differs")
    source = __import__("traffic_saved" if "__traffic_" in case_id else "saved_backing")
    measured = source.process(root, case_id, allow_diagnostic=diagnostic_test)
    pixels = audit_media(root, receipt, dimensions={name: None for name in CAMERAS} if diagnostic_test else None)
    motion = physical_result(root, {"target_checks": []})
    check = motion["physical_checks"]["maneuver"]
    if check["status"] != "met" or not motion.get("maneuver_completed"):
        raise ValueError("original reverse motion completion is not measured")
    if not diagnostic_test and motion.get("provenance_kind") != "native":
        raise ValueError("physical measurement lacks Native provenance")
    for name, expected_sha in seal["sources"].items():
        if sha(confined(root, name)) != expected_sha:
            raise ValueError("sealed original source changed during independent audit: " + name)
    return {"format": "SOURCE_AUDIT", "assignment_id": ASSIGNMENT, "case_id": case_id,
            "capture_seal_sha256": sha(root / "capture-seal.json"),
            "acquisition_sha256": measured["acquisition_sha256"],
            "source_count": len(seal["sources"]), "full_video_decode": pixels,
            "physical_maneuver": check, "provenance_kind": "synthetic_fixture" if diagnostic_test else "native",
            "diagnostic_fixture": diagnostic_test, "participant_visibility_confirmed": False,
            "legal_judgment": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--owner-release-receipt")
    parser.add_argument("--diagnostic-test", action="store_true")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    attempt = Path(args.attempt).resolve()
    if output == attempt or attempt in output.parents:
        raise ValueError("SOURCE_AUDIT must be written outside the original attempt")
    result = audit(attempt, args.case, diagnostic_test=args.diagnostic_test,
                   owner_release_receipt=args.owner_release_receipt)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print("SOURCE_AUDIT passed for exact case", args.case)
