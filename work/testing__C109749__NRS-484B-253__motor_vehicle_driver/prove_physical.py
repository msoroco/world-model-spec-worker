"""Generate source-shaped synthetic motion and lifecycle rejection fixtures."""

import hashlib
import json
from pathlib import Path

from construction import POLICIES
from physical_completion import EVENTS, assess, lifecycle
from saved_left_turn import ASSIGNMENT_ID


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def vertices(x):
    return [[x + dx, dy, z] for dx in (-0.1, 0.1)
            for dy in (-0.1, 0.1) for z in (0.0, 1.0)]


def prove(folder):
    folder.mkdir(parents=True, exist_ok=True)
    map_path = folder / "original-map.json"
    write(map_path, {"source_ref": "synthetic-map-for-checker",
                     "intersection_polygon": [[-2, -2], [2, -2], [2, 2], [-2, 2]]})
    fixtures = []
    for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
        trace = folder / (kind + "-original-trace.jsonl")
        if kind != "missing_evidence":
            xs = [-10.0, 0.0, 10.0] if kind == "complete_motion" else [-10.0, 0.0, 0.5]
            rows = [{"frame": i, "time_s": i * 0.05,
                     "ego_vertices": vertices(x), "ego_turn_committed": i == 2}
                    for i, x in enumerate(xs)]
            trace.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
        result = assess(trace, map_path)
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        assert result["physical_checks"]["maneuver"]["status"] == expected
        assert result["maneuver_completed"] == (expected == "met")
        result_path = folder / (kind + "-result.json")
        write(result_path, result)
        log = folder / (kind + "-test.log")
        log.write_text(f"{kind}: {expected}; source-bound checker passed\n", encoding="utf-8")
        fixtures.append({"kind": kind, "command": "prove_physical.py --case CASE --fixture " + kind,
                         "exit_code": 0, "log": log.name, "log_sha256": sha(log),
                         "result": result_path.name, "result_sha256": sha(result_path)})
    life = lifecycle(EVENTS, encoder_exit_codes={"overview": 0, "detail": 0},
                     restoration_verified=True)
    for altered in (EVENTS[:-2] + EVENTS[-1:], EVENTS[:-1]):
        try:
            lifecycle(altered, encoder_exit_codes={}, restoration_verified=True)
        except ValueError as error:
            assert "closed Native ownership" in str(error)
        else:
            raise AssertionError("broken lifecycle accepted")
    try:
        lifecycle(EVENTS, encoder_exit_codes={"overview": 1}, restoration_verified=True)
    except ValueError as error:
        assert "encoders and world restoration" in str(error)
    else:
        raise AssertionError("failed encoder accepted")
    log = folder / "lifecycle-test.log"
    log.write_text("ordered release accepted; early saved processing and failed encoder rejected\n", encoding="utf-8")
    life.update(log=log.name, log_sha256=sha(log))
    return fixtures, life


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    fixture_dir = root / "physical-fixtures"
    fixtures, life = prove(fixture_dir)
    manifest_path = root / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["cases"]:
        case = entry["case_id"]
        assert case.startswith(ASSIGNMENT_ID + "__") and case.rsplit("__", 1)[1] in POLICIES
        proof_path = root / "cases" / case.rsplit("__", 1)[1] / "physical-preparation.json"
        proof = {"case_id": case, "construction_sha256": entry["construction_sha256"],
                 "fixtures": [{**f, "command": f["command"].replace("CASE", case),
                               "log": "physical-fixtures/" + f["log"],
                               "result": "physical-fixtures/" + f["result"]} for f in fixtures],
                 "lifecycle": {**life, "log": "physical-fixtures/" + life["log"]},
                 "physical_acceptance_claimed": False}
        write(proof_path, proof)
        entry["physical_preparation"] = {"receipt": str(proof_path.relative_to(root)),
                                          "sha256": sha(proof_path)}
    write(manifest_path, manifest)
    print("8 exact physical fixture receipts; 3 outcomes and lifecycle rejections")
