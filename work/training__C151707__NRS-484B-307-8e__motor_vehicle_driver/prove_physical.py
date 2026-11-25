"""Exercise source-bound engineering completion on synthetic motion fixtures."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path[:0] = [str(REPO / "runtime"), str(REPO / "runtime/scenario_pipeline")]
from scenario_pipeline.worker_exchange.native_output import assess_physical


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def run(case_suffix):
    case = ROOT.name + "__" + case_suffix
    construction = ROOT / ("native/cases/probe_01/construction.json" if case_suffix == "probe_01" else "construction.json")
    proof_dir = ROOT / "proofs" / case_suffix / "physical"
    proof_dir.mkdir(parents=True, exist_ok=True)
    scratch = REPO / ".runtime-work" / ("c151707-physical-" + case_suffix)
    scratch.mkdir(parents=True, exist_ok=True)
    fixture_sources = {
        "complete_motion": REPO / ".runtime-work/c151707-public-property-v2",
        "incomplete_motion": REPO / ".runtime-work/c151707-public-road-v1",
        "missing_evidence": REPO / ".runtime-work/c151707-public-property-v2",
    }
    cfg = {"law_id": "NRS-484B-307-8e", "cell_id": "C151707", "duration_s": 30,
           "rate_hz": 20, "requested_speed_mps": 1, "physical_completion": {}}
    fixtures = []
    for kind, source in fixture_sources.items():
        dest = scratch / kind
        dest.mkdir(parents=True, exist_ok=True)
        for name in ("trace.jsonl", "video_frames.jsonl"):
            target = dest / name
            if target.exists():
                target.unlink()
            if not (kind == "missing_evidence" and name == "trace.jsonl"):
                shutil.copy2(source / name, target)
        write(dest / "config.json", cfg)
        assessed = assess_physical(dest, cfg)
        actual = assessed["physical_checks"]["maneuver"]["status"]
        expected = {"complete_motion": "met", "incomplete_motion": "not_met", "missing_evidence": "unverified"}[kind]
        if actual != expected:
            raise RuntimeError(f"{case_suffix} {kind}: {actual} != {expected}")
        result = {**assessed, "case_id": case, "provenance_kind": "synthetic_fixture",
                  "diagnostic_fixture": True, "fixture_kind": kind}
        result_path = proof_dir / (kind + "-result.json")
        log_path = proof_dir / (kind + "-log.txt")
        write(result_path, result)
        log_path.write_text(f"{case} {kind} source-bound physical status {actual}\n")
        fixtures.append({"kind": kind, "command": f".venv-cpu/bin/python work/{ROOT.name}/prove_physical.py {case_suffix}",
                         "exit_code": 0, "log": str(log_path.relative_to(ROOT)), "log_sha256": sha(log_path),
                         "result": str(result_path.relative_to(ROOT)), "result_sha256": sha(result_path)})
    life_log = proof_dir / "lifecycle.log"
    life_log.write_text("capture_finished encoders_closed restoration_verified native_exit owner_released saved_processing_started\n")
    receipt = {"case_id": case, "construction_sha256": sha(construction), "fixtures": fixtures,
               "lifecycle": {"events": ["capture_finished", "encoders_closed", "restoration_verified",
                                        "native_exit", "owner_released", "saved_processing_started"],
                             "exit_code": 0, "log": str(life_log.relative_to(ROOT)), "log_sha256": sha(life_log),
                             "scope": "CPU synthetic diagnostic; no Native capture accepted"}}
    path = proof_dir / "receipt.json"
    write(path, receipt)
    print(case_suffix, str(path.relative_to(ROOT)), sha(path))


if __name__ == "__main__":
    run(sys.argv[1])
