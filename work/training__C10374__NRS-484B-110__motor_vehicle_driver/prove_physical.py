"""Exercise source-bound route completion and lifecycle rejection on CPU fixtures."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE_PREFIX = HERE.name + "__selected_c5852cfd__condition_"
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def read_rows(path):
    if not path.is_file():
        return None
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def assess(case, actor_path, selected_rows=None):
    rows = read_rows(actor_path) if selected_rows is None else selected_rows
    sources = {"native-raw-actors.jsonl": sha(actor_path)} if actor_path.is_file() else {}
    method = "source-hashed original-frame body and speed route progress at 20 Hz"
    status = "unverified"
    details = {"official_safety_zone_designation_verified": False,
               "legal_verdict_claimed": False}
    if rows:
        frames = [row.get("native_frame") for row in rows]
        centers = [row.get("ego", {}).get("center_native_xyz_m") for row in rows]
        speeds = [row.get("ego", {}).get("speed_mps") for row in rows]
        joined = (len(rows) == 600 and all(isinstance(p, list) and len(p) == 3 for p in centers)
                  and all(isinstance(v, (int, float)) for v in speeds)
                  and frames == list(range(frames[0], frames[0] + len(frames)))
                  and all(row.get("frame") == i for i, row in enumerate(rows)))
        progress = abs(centers[-1][0] - centers[0][0]) if centers[0] and centers[-1] else 0
        moving = sum(v > 0.1 for v in speeds if isinstance(v, (int, float)))
        status = "met" if joined and progress >= 15 and moving >= 20 else "not_met"
        details.update(source_rows=len(rows), frame_join_complete=joined,
                       route_progress_m=progress, moving_samples=moving,
                       engineering_progress_threshold_m=15)
    else:
        details["missing_evidence"] = ["native-raw-actors.jsonl"]
    check = {"status": status, "method": method, "sources": sources or {"missing": "native-raw-actors.jsonl"},
             "details": details}
    return {"case_id": case, "physical_checks": {"maneuver": check},
            "maneuver_completed": status == "met",
            "realized_observables": {"route_progress_m": details["route_progress_m"],
                                     "moving_samples": details["moving_samples"]} if status == "met" else {},
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "official_safety_zone_designation_verified": False, "accepted": False}


def lifecycle(events):
    if events != EVENTS:
        raise ValueError("Saved processing precedes Native ownership closure")
    return {"events": events, "exit_code": 0}


def run():
    for suffix in ("a", "b"):
        case = CASE_PREFIX + suffix
        construction = HERE / f"selected-current-v2-condition_{suffix}-construction.json"
        root = HERE / "native/zone/offline/raw-fixtures" / f"selected_c5852cfd__condition_{suffix}/primary"
        actors = root / "native-raw-actors.jsonl"
        rows = read_rows(actors)
        assert rows and len(rows) == 600
        out = HERE / "physical" / f"condition-{suffix}"
        fixtures = []
        for kind, selected in (("complete_motion", rows), ("incomplete_motion", rows[:100]),
                               ("missing_evidence", [])):
            result = assess(case, actors, selected)
            expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                        "missing_evidence": "unverified"}[kind]
            assert result["physical_checks"]["maneuver"]["status"] == expected
            result_path = out / f"{kind}-result.json"
            log_path = out / f"{kind}.log"
            write(result_path, result)
            log_path.write_text(f"{case} {kind}: {expected}\n")
            fixtures.append({"kind": kind,
                             "command": f".venv-cpu/bin/python work/{HERE.name}/prove_physical.py",
                             "exit_code": 0, "log": str(log_path.relative_to(HERE)),
                             "log_sha256": sha(log_path), "result": str(result_path.relative_to(HERE)),
                             "result_sha256": sha(result_path)})
        assert lifecycle(EVENTS)["exit_code"] == 0
        for events in (EVENTS[:-1] + ["saved_processing_started", "owner_released"],
                       EVENTS[:-1]):
            try:
                lifecycle(events)
            except ValueError:
                pass
            else:
                raise AssertionError("Invalid lifecycle accepted")
        life_log = out / "lifecycle.log"
        life_log.write_text("Native exit and owner release precede saved processing; two invalid orders rejected\n")
        proof = {"case_id": case, "construction_sha256": sha(construction), "fixtures": fixtures,
                 "lifecycle": {**lifecycle(EVENTS), "log": str(life_log.relative_to(HERE)),
                               "log_sha256": sha(life_log)},
                 "scope": "synthetic source and lifecycle software proof only"}
        write(out / "preparation-proof.json", proof)
        print(case, "three physical classifications and lifecycle negatives passed")


if __name__ == "__main__":
    run()
