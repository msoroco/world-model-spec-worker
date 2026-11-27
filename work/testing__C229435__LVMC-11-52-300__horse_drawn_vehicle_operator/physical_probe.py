"""Source-bound three-outcome and lifecycle CPU fixture for nighttime parking."""
import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from night_parking_measurement import measure

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCES = ("context.json", "classification.json", "activity.json",
           "night-parking-trace.jsonl", "video_frames.jsonl", "night-parking-sources.json")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def lifecycle(saved_root):
    attempt = saved_root / "attempt"
    seal = read(attempt / "capture-seal.json")
    exit_record = read(attempt / "native-exit.json")
    owner = read(attempt / "owner-release.json")
    processing = read(saved_root / "derived/v0001/processing.json")
    if seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"]:
        raise ValueError("capture closure ordering differs")
    if (exit_record.get("event") != "native_exit" or
            exit_record.get("capture_seal_sha256") != sha(attempt / "capture-seal.json")):
        raise ValueError("Native exit does not bind capture seal")
    if (owner.get("event") != "owner_released" or owner.get("operator_attested") is not True
            or owner.get("native_exit_sha256") != sha(attempt / "native-exit.json")):
        raise ValueError("operator release does not bind Native exit")
    if (processing.get("passed") is not True or processing.get("recorded_only") is not True
            or processing.get("events") != ["saved_processing_started", "selected_analysis_executed", "originals_verified"]):
        raise ValueError("saved-only processing did not follow closure protocol")
    return {"events": ["capture_finished", "encoders_closed", "restoration_verified",
                       "native_exit", "owner_released", "saved_processing_started"],
            "exit_code": 0, "diagnostic_fixture": True,
            "scope": "synthetic lifecycle ordering only; no actual Native release claim"}


def outcome(saved_root, kind):
    attempt = saved_root / "attempt"
    with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c229435-physical-") as temporary:
        folder = Path(temporary)
        for name in SOURCES:
            shutil.copy2(attempt / name, folder / name)
        source_manifest = read(folder / "night-parking-sources.json")
        if kind == "incomplete_motion":
            path = folder / "night-parking-trace.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[len(rows) // 2]["subject"]["parked"] = False
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            source_manifest["sources"]["trace"]["sha256"] = sha(path)
            (folder / "night-parking-sources.json").write_text(json.dumps(source_manifest, indent=2) + "\n")
        elif kind == "missing_evidence":
            (folder / "classification.json").unlink()
        sources = {name: sha(folder / name) for name in SOURCES if (folder / name).is_file()}
        try:
            measured = measure(folder, source_manifest)
            if kind != "complete_motion":
                raise ValueError("negative physical fixture unexpectedly measured")
            if measured["elapsed_s"] != .2 or measured["parked_frame_count"] != 5:
                raise ValueError("bounded diagnostic parking interval differs")
            status, detail = "met", "joined synthetic parked interval of 0.2 seconds"
        except (FileNotFoundError, ValueError) as error:
            if kind == "complete_motion":
                raise
            expected = "incomplete continuously parked" if kind == "incomplete_motion" else "classification.json"
            if expected not in str(error):
                raise
            measured = None
            status = "not_met" if kind == "incomplete_motion" else "unverified"
            detail = str(error)
        check = {"status": status, "method": "bounded original-source diagnostic episode join",
                 "sources": sources, "detail": detail, "legal_verdict_claimed": False,
                 "physical_acceptance_claimed": False}
        return {"format": "night-parking-physical-diagnostic", "kind": kind,
                "physical_checks": {name: check for name in ("setup", "target", "maneuver")},
                "maneuver_completed": status == "met",
                "realized_observables": {"synthetic_episode_elapsed_s": measured["elapsed_s"]} if measured else {},
                "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                "physical_acceptance_claimed": False,
                "remaining": "Original 1800-second Native parking and actual pixel review"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--saved-root", required=True)
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion", "missing_evidence", "lifecycle"), required=True)
    parser.add_argument("--result")
    args = parser.parse_args(argv)
    if not args.case.startswith(ROOT.name + "__"):
        raise ValueError("exact case identity required")
    saved_root = Path(args.saved_root).resolve()
    if REPO / ".runtime-work" not in saved_root.parents:
        raise ValueError("physical source fixture must stay under .runtime-work")
    if args.kind == "lifecycle":
        print(json.dumps(lifecycle(saved_root), indent=2))
        return 0
    result = outcome(saved_root, args.kind)
    if not args.result:
        parser.error("--result required for physical outcome")
    output = Path(args.result).resolve()
    if ROOT not in output.parents or output.exists():
        raise ValueError("new physical diagnostic result belongs to own work directory")
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"kind": args.kind, "status": result["physical_checks"]["maneuver"]["status"],
                      "result": output.name}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
