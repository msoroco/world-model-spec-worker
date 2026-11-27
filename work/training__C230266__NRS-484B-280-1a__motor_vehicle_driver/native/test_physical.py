"""Exercise the runtime's source-bound physical and lifecycle gates on CPU fixtures."""

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from worker_exchange.native_output import physical_result

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main(condition):
    source = REPO / f".runtime-work/c230266-release2-{condition}-primary-compat"
    native = ROOT / "native"
    case_id = ROOT.name + "__selected_90e3f1aa__condition_" + condition
    construction = native / f"selected-{condition}-construction.json"
    output = native / f"physical-{condition}"
    output.mkdir(exist_ok=True)
    fixtures = []
    for kind, expected in (("complete_motion", "met"),
                           ("incomplete_motion", "not_met"),
                           ("missing_evidence", "unverified")):
        with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work",
                                         prefix=f"c230266-physical-{condition}-") as name:
            attempt = Path(name)
            for item in ("config.json", "trace.jsonl", "video_frames.jsonl"):
                if kind != "missing_evidence" or item != "trace.jsonl":
                    shutil.copyfile(source / item, attempt / item)
            if kind == "incomplete_motion":
                rows = [json.loads(line) for line in (attempt / "trace.jsonl").read_text().splitlines()]
                first = rows[0]["position_m"]
                for row in rows:
                    row["position_m"] = first
                (attempt / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            result = physical_result(attempt, {"target_checks": []})
            check = result["physical_checks"]["maneuver"]
            assert check["status"] == expected, (kind, check["status"])
            assert result["maneuver_completed"] == (expected == "met")
            assert result["provenance_kind"] == "synthetic_fixture"
            assert result["diagnostic_fixture"] is True
            path = output / (kind + ".json")
            write(path, result)
            fixtures.append({"kind": kind, "command":
                             f"PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python {native / 'test_physical.py'} --condition {condition}",
                             "exit_code": 0, "log": f"native/physical-{condition}/physical.log",
                             "result": str(path.relative_to(ROOT)), "result_sha256": sha(path)})
    compatibility = json.loads((source / "compatibility.json").read_text())
    assert compatibility["passed"] is True
    life = {"events": ["capture_finished", "encoders_closed", "restoration_verified",
                       "native_exit", "owner_released", "saved_processing_started"],
            "exit_code": 0, "log": f"native/physical-{condition}/physical.log",
            "synthetic_sequence_only": True,
            "source_compatibility_sha256": sha(source / "compatibility.json")}
    proof = {"format": "worker-physical-preparation", "case_id": case_id,
             "construction_sha256": sha(construction), "fixtures": fixtures,
             "lifecycle": life, "original_native_observed": False,
             "legal_acceptance_claimed": False}
    write(output / "physical-preparation.json", proof)
    print(json.dumps({"case_id": case_id, "fixture_statuses":
                      [item["kind"] for item in fixtures], "synthetic_only": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", choices=("a", "b"), required=True)
    main(parser.parse_args().condition)
