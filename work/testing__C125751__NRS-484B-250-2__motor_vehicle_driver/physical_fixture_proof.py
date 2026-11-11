"""C125751 source-shaped CPU proofs for physical classification and closure.

Native provenance here is a classifier input in a diagnostic fixture. It is not
evidence of a CARLA run or a physically accepted crossing.
"""
import argparse
import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release
from worker_exchange.common import sha


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def inputs(root, folder, entry):
    construction_path = folder / entry["construction"]
    construction = read(construction_path)
    config = json.loads(next(item["content"] for item in construction["files"]
                             if item["path"] == "config.json"))
    source = folder / ("diagnostic-sources" if entry["case_id"].endswith("signal_operative")
                       else "diagnostic-off-sources")
    write(root / "config.json", config)
    for name in ("trace.jsonl", "video_frames.jsonl", "crossing_history.jsonl"):
        shutil.copy2(source / name, root / name)
    write(root / "acquisition-provenance.json", {"provenance_kind": "native",
        "diagnostic_fixture": True, "scope": "Synthetic CPU physical-classifier fixture only"})
    return construction


def motion(folder, entry, kind, output):
    with tempfile.TemporaryDirectory(prefix="c125751-motion-") as temp:
        root = Path(temp)
        inputs(root, folder, entry)
        if kind == "incomplete_motion":
            rows = [json.loads(line) for line in (root / "crossing_history.jsonl").read_text().splitlines()]
            first = copy.deepcopy(rows[0]["ego_vertices_m"])
            for row in rows:
                row["ego_vertices_m"] = copy.deepcopy(first)
            (root / "crossing_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        elif kind == "missing_evidence":
            (root / "crossing_history.jsonl").unlink()
        result = physical_result(root, {"target_checks": []})
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        actual = result["physical_checks"]["maneuver"]["status"]
        if actual != expected or result["maneuver_completed"] != (expected == "met"):
            raise ValueError(f"Physical-classifier mismatch: {actual}, expected {expected}")
        if not result["physical_checks"]["maneuver"]["sources"]:
            raise ValueError("Physical outcome lacks original-source hashes")
        if result["diagnostic_fixture"] is not True or result["physical_acceptance_claimed"] is not False:
            raise ValueError("CPU fixture was misclassified as physical acceptance")
        if kind == "missing_evidence" and "crossing_history.jsonl" not in result["physical_checks"]["maneuver"]["missing_evidence"]:
            raise ValueError("Missing original body history not reported")
        write(output, result)
        print(json.dumps({"case_id": entry["case_id"], "fixture": kind,
                          "maneuver_status": actual, "diagnostic_fixture": True}))


def lifecycle(folder, entry, output):
    saved = folder / ("operative-process-saved-receipt.json" if entry["case_id"].endswith("signal_operative")
                      else "off-process-saved-receipt.json")
    receipt = read(saved)
    if (receipt.get("format") != "worker-saved-processing" or receipt.get("passed") is not True
            or receipt.get("recorded_only") is not True
            or receipt["analysis_revision"]["construction_sha256"] != entry["construction_sha256"]):
        raise ValueError("Current selected recorded-only saved proof missing")
    with tempfile.TemporaryDirectory(prefix="c125751-lifecycle-") as temp:
        root = Path(temp)
        construction = inputs(root, folder, entry)
        write(root / "construction.json", construction)
        (root / "runner.py").write_text(next(item["content"] for item in construction["files"]
                                          if item["path"] == "runner.py"))
        try:
            seal_capture(root, frames=1100, restoration={"restored": True}, errors=[],
                         encoder_exit_codes={"fixture_encoder": 1}, context={"diagnostic_fixture": True})
        except ValueError as error:
            if "unclosed/failed encoders" not in str(error):
                raise
        else:
            raise ValueError("Failed fixture encoder was sealed")
        seal = seal_capture(root, frames=1100, restoration={"restored": True}, errors=[],
                            encoder_exit_codes={"fixture_encoder": 0}, context={"diagnostic_fixture": True})
        try:
            acknowledge_owner_release(root, root / "owner-release.json", True)
        except ValueError as error:
            if "Native process has not exited" not in str(error):
                raise
        else:
            raise ValueError("Owner release preceded Native exit")
        exit_receipt = record_native_exit(root)
        owner = acknowledge_owner_release(root, root / "owner-release.json", True)
        if exit_receipt["capture_seal_sha256"] != sha(root / "capture-seal.json") or owner["native_exit_sha256"] != sha(root / "native-exit.json"):
            raise ValueError("Closure hash join differs")
        events = seal["events"] + [exit_receipt["event"], owner["event"], receipt["events"][0]]
        expected = ["capture_finished", "encoders_closed", "restoration_verified", "native_exit",
                    "owner_released", "saved_processing_started"]
        if events != expected:
            raise ValueError("Saved processing preceded verified closure")
        write(output, {"events": events, "diagnostic_fixture": True,
                       "failed_encoder_rejected": True, "premature_release_rejected": True,
                       "capture_seal_sha256": sha(root / "capture-seal.json"),
                       "native_exit_sha256": sha(root / "native-exit.json"),
                       "owner_release_sha256": sha(root / "owner-release.json"),
                       "saved_processing_receipt_sha256": sha(saved)})
        print(json.dumps({"case_id": entry["case_id"], "events": events,
                          "diagnostic_fixture": True}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True, choices=("complete_motion", "incomplete_motion",
                                                          "missing_evidence", "lifecycle"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = args.manifest.resolve()
    entry = next((x for x in read(manifest)["cases"] if x["case_id"] == args.case), None)
    if entry is None:
        raise ValueError("Unknown exact physical fixture case")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.kind == "lifecycle":
        lifecycle(manifest.parent, entry, args.output)
    else:
        motion(manifest.parent, entry, args.kind, args.output)


if __name__ == "__main__":
    main()
