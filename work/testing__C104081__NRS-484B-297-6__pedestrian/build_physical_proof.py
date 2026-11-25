"""Make three explicitly synthetic physical-outcome CPU fixtures per exact case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def build() -> None:
    from worker_exchange.native_output import physical_result
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, _closure
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.removeprefix(ROOT.name + "__")
        source = REPO / ".runtime-work" / f"c104081-selected-v2-compat-{suffix}-primary"
        if not (source / "result.json").is_file():
            raise ValueError("selected compatibility fixture missing: " + suffix)
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            with TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c104081-physical-") as temporary:
                temp = Path(temporary)
                for name in ("config.json", "trace.jsonl", "video_frames.jsonl"):
                    (temp / name).write_bytes((source / name).read_bytes())
                original = json.loads((source / "result.json").read_text())
                if kind == "incomplete_motion":
                    rows = [json.loads(line) for line in (temp / "trace.jsonl").read_text().splitlines()]
                    start = rows[0]["position_m"]
                    for row in rows:
                        row["position_m"] = start
                        row["position"] = dict(zip(("x", "y", "z"), start))
                    (temp / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
                elif kind == "missing_evidence":
                    (temp / "trace.jsonl").unlink()
                result = physical_result(temp, original)
                result["provenance_kind"] = "synthetic_fixture"
                result["diagnostic_fixture"] = True
                result["physical_acceptance_claimed"] = False
                result["legal_judgment"] = "unresolved"
                expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                            "missing_evidence": "unverified"}[kind]
                actual = result["physical_checks"]["maneuver"]["status"]
                if actual != expected or result["maneuver_completed"] != (expected == "met"):
                    raise ValueError(f"{suffix} {kind} physical outcome differs: {actual}")
                result_file = ROOT / f"physical-{suffix}-{kind}.json"
                write(result_file, result)
                log = ROOT / f"physical-{suffix}-{kind}.log"
                log.write_text(f"synthetic {kind}: {actual}; source-shaped measurement only\n")
                fixtures.append({"kind": kind,
                    "command": f"PYTHONPATH=runtime .venv-cpu/bin/python {ROOT.relative_to(REPO) / 'build_physical_proof.py'}",
                    "exit_code": 0, "log": log.name, "log_sha256": sha(log),
                    "result": result_file.name, "result_sha256": sha(result_file)})
        with TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c104081-lifecycle-") as temporary:
            scratch = Path(temporary)
            (scratch / "construction.json").write_bytes((source / "construction.json").read_bytes())
            (scratch / "runner.py").write_bytes((source / "runner.py").read_bytes())
            write(scratch / "capture-seal.json", {
                "events": ["capture_finished", "encoders_closed", "restoration_verified"],
                "native_revision": {"construction_sha256": sha(scratch / "construction.json"),
                                    "runner_sha256": sha(scratch / "runner.py")},
                "sources": {"construction.json": sha(scratch / "construction.json"),
                            "runner.py": sha(scratch / "runner.py")}})
            exit_receipt = record_native_exit(scratch)
            release_path = scratch / "owner-release.json"
            release = acknowledge_owner_release(scratch, release_path, True)
            _closure(scratch, release_path, "native", False)
            if exit_receipt["event"] != "native_exit" or release["event"] != "owner_released":
                raise ValueError("Native closure fixture did not reach saved-processing gate")
        life_log = ROOT / f"physical-{suffix}-lifecycle.log"
        life_log.write_text("synthetic Native closure fixture: capture_finished, encoders_closed, restoration_verified, native_exit, owner_released, saved_processing_started; _closure passed\n")
        proof = {"format": "worker-pedestrian-physical-preparation",
                 "case_id": case_id, "construction_sha256": entry["construction_sha256"],
                 "fixtures": fixtures,
                 "lifecycle": {"events": ["capture_finished", "encoders_closed",
                                          "restoration_verified", "native_exit",
                                          "owner_released", "saved_processing_started"],
                               "exit_code": 0, "log": life_log.name,
                               "log_sha256": sha(life_log)}}
        proof_file = ROOT / f"physical-{suffix}-proof.json"
        write(proof_file, proof)
        entry["physical_preparation"] = {"receipt": proof_file.name,
                                         "sha256": sha(proof_file)}
    write(manifest_path, manifest)
    print("built", len(manifest["cases"]), "synthetic physical-outcome proof sets")


if __name__ == "__main__":
    build()
