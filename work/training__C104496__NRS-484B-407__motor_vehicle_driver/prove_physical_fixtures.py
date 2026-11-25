"""Exercise three source-bound diagnostic turn outcomes per selected case.

These CPU fixtures test event assessment. They are not original CARLA captures,
body visibility findings, or a legal judgment.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work/c104496-physical-fixtures-v2"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(SCRATCH)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
    from worker_exchange.native_output import physical_result
    selected = json.loads((HERE / "selected-construction-manifest.json").read_text())
    results = []
    for entry in selected["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        source = ROOT / ".runtime-work/c104496-fixture-proof-v7" / suffix
        construction = json.loads((HERE / entry["construction"]).read_text())
        config = json.loads(next(f["content"] for f in construction["files"]
                                 if f["path"] == "config.json"))
        fixtures = []
        for kind, expected in (("complete_motion", "met"),
                               ("incomplete_motion", "not_met"),
                               ("missing_evidence", "unverified")):
            stage = SCRATCH / suffix / kind
            if stage.exists():
                raise ValueError("Use a fresh physical fixture scratch directory")
            stage.mkdir(parents=True)
            for name in ("trace.jsonl", "video_frames.jsonl",
                         "turn_history.jsonl", "curve_context.json",
                         "acquisition-provenance.json"):
                shutil.copy2(source / name, stage / name)
            write(stage / "config.json", config)
            if kind == "incomplete_motion":
                rows = (stage / "turn_history.jsonl").read_text().splitlines()
                (stage / "turn_history.jsonl").write_text("\n".join(rows[:100]) + "\n")
            if kind == "missing_evidence":
                (stage / "turn_history.jsonl").unlink()
            measured = physical_result(stage, {"case_id": entry["case_id"],
                                               "target_checks": []})
            measured["fixture_kind"] = kind
            status = measured["physical_checks"]["maneuver"]["status"]
            if (status != expected or measured["diagnostic_fixture"] is not True or
                    measured["provenance_kind"] != "synthetic_fixture" or
                    measured["maneuver_completed"] != (expected == "met")):
                raise ValueError("Physical diagnostic fixture outcome differs: " + kind)
            out = HERE / "physical" / suffix
            result = out / (kind + "-result.json")
            log = out / (kind + ".log")
            write(result, measured)
            log.write_text(json.dumps({"case_id": entry["case_id"],
                "fixture_kind": kind, "status": status,
                "source_dir": str(source.relative_to(ROOT)),
                "motion_source_sha256": sha(stage / "turn_history.jsonl")
                    if (stage / "turn_history.jsonl").is_file() else None,
                "synthetic_diagnostic": True,
                "original_visibility_verified": False},
                separators=(",", ":"), allow_nan=False) + "\n")
            fixtures.append({"kind": kind, "command":
                ".venv-cpu/bin/python work/" + HERE.name +
                "/prove_physical_fixtures.py", "exit_code": 0,
                "log": str(log.relative_to(HERE)), "log_sha256": sha(log),
                "result": str(result.relative_to(HERE)),
                "result_sha256": sha(result)})
        results.append({"case_id": entry["case_id"],
                        "construction_sha256": entry["construction_sha256"],
                        "fixtures": fixtures,
                        "synthetic_diagnostic": True,
                        "original_visibility_verified": False})
        print(json.dumps({"case": suffix, "statuses": ["met", "not_met", "unverified"]}),
              flush=True)
    write(HERE / "physical-fixtures-proof.json",
          {"format": "c104496-physical-fixtures-proof-v1", "cases": results,
           "passed": True, "original_physical_acceptance_claimed": False})


if __name__ == "__main__":
    main()
