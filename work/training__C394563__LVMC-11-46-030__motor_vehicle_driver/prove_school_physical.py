"""Exercise saved physical outcomes and owner-release ordering on CPU fixtures."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work" / "c394563-physical-fixtures"
if not str(Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()).startswith(str(REPO / ".runtime-work")):
    raise ValueError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime import")
sys.path.insert(0, str((REPO / "runtime/scenario_pipeline").resolve()))
from worker_exchange.native_output import physical_result
from worker_exchange.saved_processing import _closure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def exercise(suffix, variant=False):
    from school_warning_scene import CASE_VARIANTS
    if suffix not in CASE_VARIANTS:
        raise ValueError("Unknown school-warning exact case")
    source = (REPO / ".runtime-work" / f"c394563-variant-physical-source-{suffix}-v2") if variant else (
        REPO / ".runtime-work" / ("c394563-saved-fixture-" +
                                      ("probe1" if suffix == "probe_1" else "probe2") + "-v2"))
    if not source.is_dir():
        raise ValueError("Materialize source-shaped diagnostic first")
    construction_root = "draft-variant-exact" if variant else "draft-exact"
    construction = json.loads((ROOT / construction_root / suffix / "primary/construction.json").read_text())
    config = json.loads(next(item["content"] for item in construction["files"]
                             if item["path"] == "config.json"))
    results = []
    for kind, expected in (("complete_motion", "met"),
                           ("incomplete_motion", "not_met"),
                           ("missing_evidence", "unverified")):
        stage = SCRATCH / suffix / kind
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir(parents=True)
        shutil.copyfile(source / "video_frames.jsonl", stage / "video_frames.jsonl")
        write(stage / "config.json", config)
        if kind != "missing_evidence":
            rows = [json.loads(line) for line in (source / "trace.jsonl").read_text().splitlines()]
            if kind == "incomplete_motion":
                initial = rows[0]["position_m"]
                for row in rows:
                    row["position_m"] = initial
                    row["position"] = {"x": initial[0], "y": initial[1], "z": initial[2]}
                    row["speed_mps"] = 0.0
                    row["velocity_mps"] = [0.0, 0.0, 0.0]
            (stage / "trace.jsonl").write_text("".join(json.dumps(row, allow_nan=False) + "\n" for row in rows))
        result = physical_result(stage, {"target_checks": []})
        observed = result["physical_checks"]["maneuver"]["status"]
        if observed != expected or result["maneuver_completed"] != (expected == "met"):
            raise ValueError("Physical fixture outcome differs: " + kind)
        proof_prefix = "variant-" if variant else ""
        result_path = ROOT / "proofs" / f"{proof_prefix}{suffix}-{kind}-physical.json"
        log_path = ROOT / "proofs" / f"{proof_prefix}{suffix}-{kind}-physical.log"
        write(result_path, result)
        log_path.write_text(f"CPU diagnostic {suffix} {kind}: {observed}; no Native or legal acceptance\n")
        results.append({"kind": kind,
            "command": "SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c394563-physical-root "
                       "TMPDIR=$PWD/.runtime-work .venv-cpu/bin/python -B work/" + ROOT.name +
                       "/prove_school_physical.py " + suffix + (" variant" if variant else ""),
            "exit_code": 0, "log": str(log_path.relative_to(ROOT)),
            "log_sha256": sha(log_path), "result": str(result_path.relative_to(ROOT)),
            "result_sha256": sha(result_path)})
    life_stage = SCRATCH / suffix / "lifecycle"
    if life_stage.exists():
        shutil.rmtree(life_stage)
    life_stage.mkdir(parents=True)
    (life_stage / "construction.json").write_text(json.dumps(construction) + "\n")
    (life_stage / "trace.jsonl").write_text("{\"frame\":1}\n")
    seal = {"events": ["capture_finished", "encoders_closed", "restoration_verified"],
            "sources": {"trace.jsonl": sha(life_stage / "trace.jsonl")},
            "native_revision": {"construction_sha256": sha(life_stage / "construction.json")}}
    write(life_stage / "capture-seal.json", seal)
    write(life_stage / "native-exit.json", {"event": "native_exit",
          "capture_seal_sha256": sha(life_stage / "capture-seal.json"),
          "native_revision": seal["native_revision"]})
    owner = life_stage / "owner-release.json"
    write(owner, {"event": "owner_released", "operator_attested": True,
                  "native_construction_sha256": sha(life_stage / "construction.json"),
                  "native_exit_sha256": sha(life_stage / "native-exit.json")})
    _closure(life_stage, owner, "native", False)
    try:
        _closure(life_stage, None, "native", False)
    except ValueError as error:
        if "owner-release" not in str(error):
            raise
    else:
        raise ValueError("Missing owner release was accepted")
    log_path = ROOT / "proofs" / f"{'variant-' if variant else ''}{suffix}-lifecycle.log"
    log_path.write_text("CPU lifecycle sequence verified; missing owner release rejected\n")
    proof = {"format": "worker-physical-preparation-proof",
             "case_id": ROOT.name + "__" + suffix,
             "construction_sha256": sha(ROOT / construction_root / suffix / "primary/construction.json"),
             "fixtures": results,
             "lifecycle": {"events": ["capture_finished", "encoders_closed",
                "restoration_verified", "native_exit", "owner_released",
                "saved_processing_started"], "exit_code": 0,
                "log": str(log_path.relative_to(ROOT)), "log_sha256": sha(log_path)},
             "synthetic_diagnostic_only": True}
    proof_path = ROOT / "proofs" / f"{'variant-' if variant else ''}{suffix}-physical-preparation.json"
    write(proof_path, proof)
    return {"proof": str(proof_path.relative_to(ROOT)), "sha256": sha(proof_path)}


if __name__ == "__main__":
    print(json.dumps(exercise(sys.argv[1], len(sys.argv) > 2 and sys.argv[2] == "variant")))
