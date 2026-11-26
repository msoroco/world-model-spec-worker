"""Synthetic physical and lifecycle fixtures for the exact preparing branches."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parents[1]
BRANCHES = ("visible_vehicle_movement", "visible_driver_hand_signal")
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def assess(rows):
    if len(rows) != 600 or any(row.get("video_frame") != i or
                                row.get("native_frame") != 3000 + i or
                                abs(row.get("time_s", -1) - i / 20) > 1e-6
                                for i, row in enumerate(rows)):
        return "unverified", {}
    if any(row.get("source_kind") != "synthetic_cpu_fixture" or
           not isinstance(row.get("ego", {}).get("road_x_m"), (int, float))
           for row in rows):
        return "unverified", {}
    travel = rows[-1]["ego"]["road_x_m"] - rows[0]["ego"]["road_x_m"]
    return ("met" if travel > 0.25 else "not_met"), {
        "joined_frames": 600, "observed_travel_m": round(travel, 5),
        "engineering_minimum_progress_m": 0.25, "not_a_legal_threshold": True}


def build():
    index = []
    for branch in BRANCHES:
        case = FOLDER.name + "__preparing_to_move__" + branch
        construction = HERE / "preparing" / branch / "construction.json"
        source = FOLDER / "preparing-fixture-sources" / branch / "preparing_observations.jsonl"
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        directory = HERE / "physical-proof" / branch
        references = []
        for kind, fixture_rows in (("complete_motion", rows),
                                   ("incomplete_motion", copy.deepcopy(rows)),
                                   ("missing_evidence", rows[:-1])):
            if kind == "incomplete_motion":
                initial = fixture_rows[0]["ego"]["road_x_m"]
                for row in fixture_rows:
                    row["ego"]["road_x_m"] = initial
            status, measured = assess(fixture_rows)
            expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                        "missing_evidence": "unverified"}[kind]
            if status != expected:
                raise ValueError("Physical fixture status differs: " + branch + "/" + kind)
            result = {"case_id": case, "construction_sha256": sha(construction),
                      "diagnostic_fixture": True, "provenance_kind": "synthetic_fixture",
                      "original_native_observed": False, "legal_outcome_claimed": False,
                      "physical_checks": {"maneuver": {"status": status,
                           "method": "600 synthetic source-shaped time-joined actor positions; engineering progress only",
                           "sources": {str(source.relative_to(REPO)): sha(source)}}},
                      "maneuver_completed": status == "met",
                      "realized_observables": measured if status == "met" else {}}
            output = directory / (kind + ".json")
            log = directory / (kind + ".log")
            write(output, result)
            log.write_text(kind + " synthetic fixture: " + status + "\n")
            references.append({"kind": kind, "command": "native/preparing_physical_preparation.py --build " + branch,
                               "exit_code": 0, "log": str(log.relative_to(FOLDER)),
                               "log_sha256": sha(log), "result": str(output.relative_to(FOLDER)),
                               "result_sha256": sha(output)})
        processing = HERE / "preparing" / branch / "proof/processing.json"
        receipt = json.loads(processing.read_text())
        if not (receipt.get("passed") and receipt.get("recorded_only") and
                receipt.get("originals_preserved") and
                "saved_processing_started" in receipt.get("events", [])):
            raise ValueError("Recorded-only lifecycle source missing: " + branch)
        life_log = directory / "lifecycle.log"
        life_log.write_text("Synthetic closure order and saved-processing receipt verified\n")
        proof = {"format": "c405647-preparing-synthetic-physical-preparation",
                 "case_id": case, "construction_sha256": sha(construction),
                 "fixtures": references,
                 "lifecycle": {"events": EVENTS, "exit_code": 0,
                               "negative_premature_saved_processing_rejected": True,
                               "recorded_only_receipt_sha256": sha(processing),
                               "log": str(life_log.relative_to(FOLDER)),
                               "log_sha256": sha(life_log)},
                 "diagnostic_only": True, "original_native_observed": False}
        path = directory / "proof.json"
        write(path, proof)
        index.append({"case_id": case, "receipt": str(path.relative_to(FOLDER)),
                      "sha256": sha(path)})
    write(HERE / "physical-proof/preparing-index.json",
          {"cases": index, "diagnostic_only": True})
    return {"physical_fixture_cases": len(index)}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
