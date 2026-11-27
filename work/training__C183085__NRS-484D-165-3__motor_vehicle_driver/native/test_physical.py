"""Exercise the pinned generic physical and lifecycle gates on CPU fixtures."""

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


def main(suffix):
    source = REPO / (".runtime-work/c183085-compat-witness-v3" if suffix == "witness_1" else ".runtime-work/c183085-compat-v3-" + suffix)
    native = ROOT / "native"
    case_id = ROOT.name + "__" + suffix
    construction = native / ("selected-" + suffix + "-construction.json")
    output = native / ("physical-" + suffix)
    output.mkdir(exist_ok=True)
    fixtures = []
    for kind, expected in (("complete_motion", "met"),
                           ("incomplete_motion", "not_met"),
                           ("missing_evidence", "unverified")):
        with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work",
                                         prefix="c183085-physical-" + suffix + "-") as temporary:
            attempt = Path(temporary)
            for name in ("config.json", "trace.jsonl", "video_frames.jsonl"):
                if kind != "missing_evidence" or name != "trace.jsonl":
                    shutil.copyfile(source / name, attempt / name)
            if kind == "complete_motion":
                rows = [json.loads(line) for line in (attempt / "trace.jsonl").read_text().splitlines()]
                for i, row in enumerate(rows):
                    step = i * .20
                    row["position_m"][0] += step
                    row["position"]["x"] += step
                    row["speed_mps"] = 4
                    row["speed_mph"] = 4 * 2.2369362921
                (attempt / "trace.jsonl").write_text(
                    "".join(json.dumps(row) + "\n" for row in rows))
            result = physical_result(attempt, {"target_checks": []})
            check = result["physical_checks"]["maneuver"]
            assert check["status"] == expected, (kind, check["status"])
            assert result["maneuver_completed"] == (expected == "met")
            assert result["provenance_kind"] == "synthetic_fixture"
            assert result["diagnostic_fixture"] is True
            path = output / (kind + ".json")
            write(path, result)
            fixtures.append({"kind": kind, "command":
                "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=runtime/scenario_pipeline "
                ".venv-cpu/bin/python work/" + ROOT.name +
                "/native/test_physical.py --suffix " + suffix,
                "exit_code": 0, "log": "native/physical-" + suffix + "/physical.log",
                "result": str(path.relative_to(ROOT)), "result_sha256": sha(path)})
    compatibility = json.loads((source / "compatibility.json").read_text())
    assert compatibility["passed"] is True
    life = {"events": ["capture_finished", "encoders_closed", "restoration_verified",
                       "native_exit", "owner_released", "saved_processing_started"],
            "exit_code": 0, "log": "native/physical-" + suffix + "/physical.log",
            "synthetic_sequence_only": True,
            "source_compatibility_sha256": sha(source / "compatibility.json")}
    proof = {"format": "worker-physical-preparation", "case_id": case_id,
             "construction_sha256": sha(construction), "fixtures": fixtures,
             "lifecycle": life, "original_native_observed": False,
             "legal_acceptance_claimed": False,
             "limitation": "Pinned generic travel-progress criterion is not a stopped-shoulder or lamp-completion criterion"}
    write(output / "physical-preparation.json", proof)
    print(json.dumps({"case_id": case_id, "fixture_statuses":
                      [item["kind"] for item in fixtures], "synthetic_only": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--suffix", required=True)
    main(parser.parse_args().suffix)
