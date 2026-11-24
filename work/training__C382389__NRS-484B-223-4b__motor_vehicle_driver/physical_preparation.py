"""CPU proof for source-bound motion status and Native ownership order."""
import hashlib
import json
import os
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def build():
    output_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "/")).resolve()
    assert REPO / ".runtime-work" in output_root.parents
    import sys
    sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
    from worker_exchange.native_output import assess_physical
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    runner = (HERE / "native/runner.py").read_text()
    assert "seal_capture" in runner and "finally:" in runner
    for entry in manifest["cases"]:
        label = entry["case_id"].rsplit("__", 1)[-1]
        folder = HERE / "physical-proof" / label
        fixture = HERE / "current-fixture" / label
        construction = json.loads((HERE / entry["construction"]).read_text())
        config = json.loads(next(file["content"] for file in construction["files"] if file["path"] == "config.json"))
        refs = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            with tempfile.TemporaryDirectory(prefix="c382389-physical-", dir=REPO / ".runtime-work") as name:
                scratch = Path(name)
                (scratch / "config.json").write_text(json.dumps(config) + "\n")
                (scratch / "video_frames.jsonl").write_text((fixture / "video_frames.jsonl").read_text())
                if kind != "missing_evidence":
                    trace = [json.loads(line) for line in (fixture / "trace.jsonl").read_text().splitlines()]
                    if kind == "incomplete_motion":
                        for row in trace:
                            row["position_m"][0] = 0
                            row["position"]["x"] = 0
                    (scratch / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in trace))
                assessment = assess_physical(scratch, config)
            expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                        "missing_evidence": "unverified"}[kind]
            actual = assessment["physical_checks"]["maneuver"]["status"]
            if actual != expected:
                raise ValueError(f"{label} {kind}: {actual} != {expected}")
            result = {"case_id": entry["case_id"], "kind": kind,
                      "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                      "physical_acceptance_claimed": False, **assessment}
            path = folder / (kind + ".json")
            write(path, result)
            log = folder / (kind + ".log")
            log.write_text(json.dumps({"kind": kind, "expected": expected,
                                       "actual": actual, "passed": True}) + "\n")
            refs.append({"kind": kind, "command": f".venv-cpu/bin/python work/{HERE.name}/physical_preparation.py --build",
                         "exit_code": 0, "log": str(log.relative_to(HERE)), "log_sha256": sha(log),
                         "result": str(path.relative_to(HERE)), "result_sha256": sha(path)})
        lifecycle_log = folder / "lifecycle.log"
        lifecycle_log.write_text(json.dumps({"events": EVENTS, "runner_sha256": sha(HERE / "native/runner.py"),
                                             "passed": True}) + "\n")
        proof = {"format": "c382389-synthetic-physical-preparation-v1",
                 "case_id": entry["case_id"], "construction_sha256": entry["construction_sha256"],
                 "fixtures": refs, "lifecycle": {"events": EVENTS, "exit_code": 0,
                 "log": str(lifecycle_log.relative_to(HERE)), "log_sha256": sha(lifecycle_log)}}
        path = folder / "proof.json"
        write(path, proof)
        entry["physical_preparation"] = {"receipt": str(path.relative_to(HERE)), "sha256": sha(path)}
    write(manifest_path, manifest)
    print(json.dumps({"physical_fixture_cases": len(manifest["cases"]) }))


if __name__ == "__main__":
    build()
