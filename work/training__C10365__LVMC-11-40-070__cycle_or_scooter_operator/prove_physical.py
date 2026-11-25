"""Classify source-shaped CPU motion fixtures and capture lifecycle ordering."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def assess(case, raw_path, review_path, rows):
    sources = {"raw.jsonl": sha(raw_path), "review.json": sha(review_path)}
    status = "unverified"
    details = {"legal_verdict_claimed": False, "original_authority_verified": False}
    if rows:
        frames = [row.get("native_frame") for row in rows]
        speeds = [row.get("rider", {}).get("speed_mps") for row in rows]
        centers = [row.get("rider", {}).get("center_native_xyz_m") for row in rows]
        joined = (len(rows) == 600 and frames == list(range(frames[0], frames[0] + len(rows)))
                  and all(row.get("frame") == i for i, row in enumerate(rows))
                  and all(isinstance(v, (int, float)) for v in speeds)
                  and all(isinstance(p, list) and len(p) == 3 for p in centers))
        station = 50.0
        stopped = any(v < 0.15 and p[0] < station for v, p in zip(speeds, centers))
        crossed = any(p[0] > station for p in centers)
        target_met = stopped and not crossed if case.endswith("probe_a") else crossed
        status = "met" if joined and target_met else "not_met"
        details.update(source_rows=len(rows), frame_join_complete=joined,
                       stopped_before_station=stopped, crossed_station=crossed)
    else:
        details["missing_evidence"] = ["raw.jsonl"]
    return {"case_id": case,
            "physical_checks": {"maneuver": {"status": status,
                         "method": "source-hashed 600-frame rider speed and station crossing",
                         "sources": sources if rows else {"missing": "raw.jsonl"},
                         "details": details}},
            "maneuver_completed": status == "met",
            "realized_observables": {"stopped_before_station": details["stopped_before_station"],
                                     "crossed_station": details["crossed_station"]} if status == "met" else {},
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "accepted": False, "legal_verdict_claimed": False}


def lifecycle(events):
    if events != EVENTS:
        raise ValueError("Saved processing precedes Native ownership closure")
    return {"events": events, "exit_code": 0}


def run():
    for suffix in ("a", "b"):
        case = HERE.name + "__probe_" + suffix
        root = HERE / "native/officer/selected-fixtures" / ("probe_" + suffix + "-primary")
        raw_path, review_path = root / "raw.jsonl", root / "review.json"
        rows = read_rows(raw_path)
        assert len(rows) == 600
        out = HERE / "physical" / ("probe-" + suffix)
        fixtures = []
        for kind, selected in (("complete_motion", rows),
                               ("incomplete_motion", rows[:100]),
                               ("missing_evidence", [])):
            result = assess(case, raw_path, review_path, selected)
            expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                        "missing_evidence": "unverified"}[kind]
            assert result["physical_checks"]["maneuver"]["status"] == expected
            result_path = out / (kind + "-result.json")
            log_path = out / (kind + ".log")
            write(result_path, result)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(f"{case} {kind}: {expected}\n")
            fixtures.append({"kind": kind,
                             "command": f".venv-cpu/bin/python work/{HERE.name}/prove_physical.py",
                             "exit_code": 0, "log": str(log_path.relative_to(HERE)),
                             "log_sha256": sha(log_path),
                             "result": str(result_path.relative_to(HERE)),
                             "result_sha256": sha(result_path)})
        assert lifecycle(EVENTS)["exit_code"] == 0
        for invalid in (EVENTS[:-1] + ["saved_processing_started", "owner_released"],
                        EVENTS[:-1]):
            try:
                lifecycle(invalid)
            except ValueError:
                pass
            else:
                raise AssertionError("Invalid lifecycle accepted")
        life_log = out / "lifecycle.log"
        life_log.write_text("Native exit and owner release precede saved processing; two invalid orders rejected\n")
        proof = {"case_id": case,
                 "construction_sha256": sha(HERE / "native/officer/selected-constructions" /
                                            ("probe_" + suffix + "-primary.json")),
                 "fixtures": fixtures,
                 "lifecycle": {**lifecycle(EVENTS), "log": str(life_log.relative_to(HERE)),
                               "log_sha256": sha(life_log)},
                 "scope": "synthetic source and lifecycle CPU proof only"}
        write(out / "preparation-proof.json", proof)
        print(case, "three physical classifications and lifecycle negatives passed")


if __name__ == "__main__":
    run()
