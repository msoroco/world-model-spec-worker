"""Exercise pinned physical outcome checker on exact synthetic source histories."""

import argparse
import base64
import hashlib
import io
import json
import sys
import tempfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release

STEMS = {"entry_before_red": "primary", "entry_at_red": "at-red",
         "entry_after_red": "after-red", "stops_on_yellow": "yellow-stop"}
EXPECTED = {"complete_motion": "met", "incomplete_motion": "not_met",
            "missing_evidence": "unverified"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def saved_primary(case_id):
    outer = json.loads((HERE / "saved-processing-receipts.json").read_text())
    raw = zlib.decompress(base64.b64decode(outer["payload"]))
    if hashlib.sha256(raw).hexdigest() != outer["uncompressed_sha256"]:
        raise ValueError("Current saved receipt archive changed")
    rows = json.loads(raw)["receipts"]
    return next(row["receipt"] for row in rows if
                row["receipt"]["case_id"] == case_id and row["receipt"]["candidate_id"] == "primary")


def run(suffix, kind, output):
    if suffix not in STEMS or kind not in (*EXPECTED, "lifecycle"):
        raise ValueError("Unknown exact case or physical fixture")
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    case_id = HERE.name + "__" + suffix
    entry = next(item for item in manifest["cases"] if item["case_id"] == case_id)
    construction = json.loads((HERE / entry["construction"]).read_text())
    config = json.loads(next(item["content"] for item in construction["files"]
                             if item["path"] == "config.json"))
    recipe = json.loads((REPO / entry["fixture_recipe"]).read_text())
    generator = REPO / recipe["generator"]["source"]
    source = json.loads(generator.read_text())
    with tempfile.TemporaryDirectory(prefix="c158196-physical-") as temp:
        root = Path(temp)
        (root / "config.json").write_text(json.dumps(config, indent=2) + "\n")
        for name in ("junction_context.json", "signal_vehicle_history.jsonl",
                     "trace.jsonl", "video_frames.jsonl"):
            if name in source["files"]:
                (root / name).write_text(source["files"][name])
        (root / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "physical_acceptance_claimed": False}) + "\n")
        if kind == "lifecycle":
            receipt = saved_primary(case_id)
            if (receipt.get("passed") is not True or receipt.get("recorded_only") is not True or
                    receipt.get("analysis_revision", {}).get("construction_sha256") !=
                    entry["construction_sha256"]):
                raise ValueError("Current selected saved-only receipt required")
            (root / "construction.json").write_text(json.dumps(construction, indent=2) + "\n")
            (root / "runner.py").write_text(next(item["content"] for item in construction["files"]
                                                 if item["path"] == "runner.py"))
            (root / "acquisition-provenance.json").write_text(json.dumps({
                "provenance_kind": "native", "diagnostic_fixture": True,
                "physical_acceptance_claimed": False,
                "scope": "Synthetic ownership lifecycle CPU fixture only"}) + "\n")
            resource = io.StringIO("diagnostic encoder")
            resource.close()
            if not resource.closed:
                raise ValueError("Diagnostic encoder still owns resource")
            seal = seal_capture(root, frames=900, restoration={"restored": True, "fixture_only": True},
                                errors=[], encoder_exit_codes={"diagnostic_encoder": 0})
            exited = record_native_exit(root)
            released = acknowledge_owner_release(root, root / "owner-release.json", True)
            events = seal["events"] + [exited["event"], released["event"], receipt["events"][0]]
            expected = ["capture_finished", "encoders_closed", "restoration_verified",
                        "native_exit", "owner_released", "saved_processing_started"]
            if events != expected:
                raise ValueError("Saved processing began before owner release")
            report = {"events": events, "diagnostic_fixture": True,
                      "saved_processing_receipt_sha256": hashlib.sha256(
                          (json.dumps(receipt, indent=2) + "\n").encode()).hexdigest(),
                      "capture_seal_sha256": sha(root / "capture-seal.json"),
                      "native_exit_sha256": sha(root / "native-exit.json"),
                      "owner_release_sha256": sha(root / "owner-release.json")}
            output = Path(output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps({"case_id": case_id, "kind": kind, "events": events,
                              "physical_acceptance_claimed": False}, sort_keys=True))
            return
        history = root / "signal_vehicle_history.jsonl"
        if kind == "incomplete_motion":
            rows = [json.loads(line) for line in history.read_text().splitlines() if line.strip()]
            first = rows[0]["ego_body_vertices_xy_m"]
            for row in rows:
                row["ego_body_vertices_xy_m"] = first
                row["ego_speed_mps"] = 0.0
            history.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))
        elif kind == "missing_evidence":
            history.unlink()
        report = physical_result(root, {"target_checks": [], "realized_observables": {},
                                        "setup_confirmed": False, "behavior_attempted": False,
                                        "maneuver_completed": False})
        status = report["physical_checks"]["maneuver"]["status"]
        if (status != EXPECTED[kind] or report.get("maneuver_completed") != (status == "met") or
                report.get("provenance_kind") != "synthetic_fixture" or
                report.get("diagnostic_fixture") is not True or
                report.get("physical_acceptance_claimed") is not False):
            raise ValueError("Pinned physical checker returned wrong diagnostic state: " + status)
        if status == "met" and not report.get("realized_observables"):
            raise ValueError("Complete motion lacks source-measured observables")
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"case_id": case_id, "kind": kind, "status": status,
                          "physical_acceptance_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=STEMS, required=True)
    parser.add_argument("--kind", choices=(*EXPECTED, "lifecycle"), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.case, args.kind, args.output)
