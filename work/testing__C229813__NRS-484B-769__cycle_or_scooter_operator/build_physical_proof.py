"""Exercise source-bound physical completion and Native closure on CPU fixtures."""

import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work" / "c229813-owner"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def main():
    if not os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "").startswith(str(REPO / ".runtime-work")):
        raise ValueError("SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work")
    from worker_exchange.native_output import physical_result
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, _closure
    manifest_path = ROOT / "execution-manifest.draft.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.removeprefix(ROOT.name + "__")
        source = SCRATCH / "compat-all-v2" / (suffix + "-primary")
        if not (source / "result.json").is_file():
            raise ValueError("positive source-shaped compatibility fixture missing: " + suffix)
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            with TemporaryDirectory(dir=SCRATCH, prefix="physical-") as temporary:
                temp = Path(temporary)
                for name in ("config.json", "trace.jsonl", "video_frames.jsonl"):
                    (temp / name).write_bytes((source / name).read_bytes())
                original = json.loads((source / "result.json").read_text())
                if kind != "missing_evidence":
                    rows = [json.loads(line) for line in (temp / "trace.jsonl").read_text().splitlines()]
                    start = rows[0]["position_m"]
                    for index, row in enumerate(rows):
                        row["position_m"] = [start[0] + (index if kind == "complete_motion" else 0),
                                             start[1], start[2]]
                    (temp / "trace.jsonl").write_text("".join(
                        json.dumps(row, sort_keys=True) + "\n" for row in rows))
                else:
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
                    raise ValueError(f"{suffix} {kind}: expected {expected}, got {actual}")
                result_path = ROOT / f"physical-{suffix}-{kind}.json"
                write(result_path, result)
                log = ROOT / f"physical-{suffix}-{kind}.log"
                log.write_text(f"synthetic source-shaped {kind}: {actual}\n")
                fixtures.append({"kind": kind,
                    "command": f"PYTHONPATH=runtime .venv-cpu/bin/python work/{ROOT.name}/build_physical_proof.py",
                    "exit_code": 0, "log": log.name, "log_sha256": sha(log),
                    "result": result_path.name, "result_sha256": sha(result_path)})
        with TemporaryDirectory(dir=SCRATCH, prefix="lifecycle-") as temporary:
            temp = Path(temporary)
            for name in ("construction.json", "runner.py"):
                (temp / name).write_bytes((source / name).read_bytes())
            write(temp / "capture-seal.json", {
                "events": ["capture_finished", "encoders_closed", "restoration_verified"],
                "native_revision": {"construction_sha256": sha(temp / "construction.json"),
                                    "runner_sha256": sha(temp / "runner.py")},
                "sources": {"construction.json": sha(temp / "construction.json"),
                            "runner.py": sha(temp / "runner.py")}})
            record_native_exit(temp)
            release = temp / "owner-release.json"
            acknowledge_owner_release(temp, release, True)
            _closure(temp, release, "native", False)
        life_log = ROOT / f"physical-{suffix}-lifecycle.log"
        life_log.write_text("synthetic capture_finished, encoders_closed, restoration_verified, native_exit, owner_released, saved_processing_started; closure passed\n")
        proof = {"format": "worker-cycle-signal-physical-preparation", "case_id": case_id,
            "construction_sha256": entry["construction_sha256"], "fixtures": fixtures,
            "lifecycle": {"events": ["capture_finished", "encoders_closed",
                "restoration_verified", "native_exit", "owner_released",
                "saved_processing_started"], "exit_code": 0,
                "log": life_log.name, "log_sha256": sha(life_log)}}
        proof_path = ROOT / f"physical-{suffix}-proof.json"
        write(proof_path, proof)
        entry["physical_preparation"] = {"receipt": proof_path.name, "sha256": sha(proof_path)}
    write(manifest_path, manifest)
    print("built", len(manifest["cases"]), "source-shaped physical/lifecycle CPU fixtures")


if __name__ == "__main__":
    main()
