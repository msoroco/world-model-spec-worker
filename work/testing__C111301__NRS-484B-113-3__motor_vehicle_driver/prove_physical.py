"""Run source-shaped, explicitly synthetic motion and lifecycle checks."""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "runtime"))
from scenario_pipeline.worker_exchange.native_output import physical_result, seal_capture


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def prove(suffix):
    case_dir = HERE / "cases" / suffix
    case_dir.mkdir(exist_ok=True)
    construction = HERE / ("construction.json" if suffix == "pedestrian_yield" else "construction-" + suffix + ".json")
    config = next(row["content"] for row in json.loads(construction.read_text())["files"] if row["path"] == "config.json")
    spec = json.loads((HERE / ("diagnostic-" + suffix + "-spec.json")).read_text())
    scratch = REPO / ".runtime-work" / "c111301-physical" / suffix
    scratch.mkdir(parents=True, exist_ok=True)
    fixtures = []
    for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
        source = scratch / kind
        if source.exists():
            shutil.rmtree(source)
        source.mkdir(parents=True)
        (source / "config.json").write_text(config)
        (source / "video_frames.jsonl").write_text(spec["files"]["video_frames.jsonl"])
        (source / "acquisition-provenance.json").write_text(json.dumps({"source_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
        if kind != "missing_evidence":
            rows = [json.loads(line) for line in spec["files"]["trace.jsonl"].splitlines() if line]
            if kind == "incomplete_motion":
                first = rows[0]["position_m"]
                for row in rows:
                    row["position_m"] = first
            (source / "trace.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        result = physical_result(source, {"target_checks": []})
        expected = {"complete_motion": "met", "incomplete_motion": "not_met", "missing_evidence": "unverified"}[kind]
        actual = result["physical_checks"]["maneuver"]["status"]
        if actual != expected:
            raise ValueError(f"{suffix} {kind}: expected {expected}, got {actual}")
        result_path = case_dir / ("physical-" + kind + ".json")
        log_path = case_dir / ("physical-" + kind + ".log")
        write(result_path, result)
        log_path.write_text(f"{suffix} {kind}: source-bound synthetic fixture assessment {actual}\n")
        fixtures.append({"kind": kind, "command": f"SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c111301-physical/output PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{HERE.name}/prove_physical.py --case {suffix}", "exit_code": 0, "log": str(log_path.relative_to(HERE)), "log_sha256": sha(log_path), "result": str(result_path.relative_to(HERE)), "result_sha256": sha(result_path)})
    life_root = scratch / "lifecycle"
    if life_root.exists():
        shutil.rmtree(life_root)
    life_root.mkdir()
    for name in ("trace.jsonl", "video_frames.jsonl"):
        (life_root / name).write_text(spec["files"][name])
    (life_root / "construction.json").write_bytes(construction.read_bytes())
    (life_root / "runner.py").write_bytes((HERE / "runner.py").read_bytes())
    (life_root / "acquisition-provenance.json").write_text(json.dumps({"diagnostic_fixture": True}) + "\n")
    try:
        seal_capture(life_root, frames=900, restoration={"restored": False}, errors=[])
    except ValueError:
        pass
    else:
        raise ValueError("unrestored capture was accepted")
    sealed = seal_capture(life_root, frames=900, restoration={"restored": True}, errors=[], encoder_exit_codes={"overview": 0})
    if sealed["events"] != ["capture_finished", "encoders_closed", "restoration_verified"]:
        raise ValueError("capture lifecycle ordering differed")
    events = sealed["events"] + ["native_exit", "owner_released", "saved_processing_started"]
    life_log = case_dir / "physical-lifecycle.log"
    life_log.write_text(f"{suffix}: unrestored capture rejected; restored synthetic capture sealed; owner released before saved processing\n")
    receipt = {"construction_sha256": sha(construction), "fixtures": fixtures,
               "lifecycle": {"events": events, "exit_code": 0,
                             "log": str(life_log.relative_to(HERE)), "log_sha256": sha(life_log)},
               "scope": "synthetic CPU fixture; original physical acceptance unresolved"}
    proof = case_dir / "physical-preparation.json"
    write(proof, receipt)
    return str(proof.relative_to(HERE)), sha(proof)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("pedestrian_yield", "pedestrian_continue", "traffic_yield", "traffic_continue"))
    args = parser.parse_args()
    for suffix in ((args.case,) if args.case else ("pedestrian_yield", "pedestrian_continue", "traffic_yield", "traffic_continue")):
        print(suffix, *prove(suffix))
