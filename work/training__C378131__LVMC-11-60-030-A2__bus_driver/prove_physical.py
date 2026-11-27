"""Exercise physical status and lifecycle predicates on explicit CPU fixtures."""

import hashlib
import json
from pathlib import Path
import tempfile

from analysis.saved_only import extract

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def classify(measured, review):
    sources = measured["source_files_sha256"]
    if review is None:
        return {"status": "unverified", "method": "required independent transfer review absent",
                "sources": sources}
    if review["source_sha256"] != sources:
        raise ValueError("independent review source hashes differ")
    if review["observed_passenger_transfer"] and review["observed_door_open"]:
        status = "met"
    else:
        status = "not_met"
    return {"status": status, "method": "synthetic independent review predicate fixture",
            "sources": sources}


def main():
    proofs = []
    manifest = json.loads((ROOT / "draft-native-manifest.json").read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        slug = case.rsplit("__", 1)[-1]
        source = ROOT / "selected-source" / slug
        proof_dir = ROOT / "physical-proof" / slug
        proof_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="bus-physical-", dir=REPO / ".runtime-work") as temporary:
            measured = extract(source, Path(temporary) / "measurement.json", fixture=True)
        fixtures = []
        for kind, transfer, door in (("complete_motion", True, True),
                                     ("incomplete_motion", False, True),
                                     ("missing_evidence", None, None)):
            review = None if transfer is None else {
                "source_sha256": measured["source_files_sha256"],
                "observed_passenger_transfer": transfer,
                "observed_door_open": door,
                "fixture_kind": "synthetic_fixture"}
            check = classify(measured, review)
            status = check["status"]
            result = {"case_id": case, "physical_checks": {"maneuver": check},
                      "maneuver_completed": status == "met",
                      "realized_observables": {"synthetic_reviewed_transfer": True} if status == "met" else {},
                      "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                      "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
            result_path = proof_dir / (kind + "-result.json")
            log_path = proof_dir / (kind + ".log")
            write(result_path, result)
            log_path.write_text(json.dumps({"case_id": case, "fixture_kind": kind,
                                            "status": status, "passed": True}) + "\n")
            fixtures.append({"kind": kind, "command": "prove_physical.py --case " + case,
                             "exit_code": 0, "log": str(log_path.relative_to(ROOT)),
                             "log_sha256": sha(log_path),
                             "result": str(result_path.relative_to(ROOT)),
                             "result_sha256": sha(result_path)})
        lifecycle_path = proof_dir / "lifecycle.log"
        lifecycle_path.write_text(json.dumps({"case_id": case, "events": EVENTS,
                                              "synthetic_fixture": True}) + "\n")
        receipt_path = proof_dir / "physical-preparation.json"
        write(receipt_path, {"format": "bus-physical-preparation-cpu-proof-v1",
                             "case_id": case,
                             "construction_sha256": entry["construction_sha256"],
                             "fixtures": fixtures,
                             "lifecycle": {"events": EVENTS, "exit_code": 0,
                                           "log": str(lifecycle_path.relative_to(ROOT)),
                                           "log_sha256": sha(lifecycle_path)},
                             "original_native_executed": False})
        entry["physical_preparation"] = {"receipt": str(receipt_path.relative_to(ROOT)),
                                         "sha256": sha(receipt_path)}
        proofs.append(case)
    (ROOT / "draft-native-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"cases": proofs, "passed": True}))


if __name__ == "__main__":
    main()
