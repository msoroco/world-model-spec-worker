"""Independent raw-source and controlled-comparison audit of six saved packages."""
import hashlib
import json
import math
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def main():
    summary = json.loads((HERE / "saved-package-summary.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    cases = {c["case_id"]: c for c in plan["cases"]}
    assert len(summary["records"]) == 6 and not summary["selected"] and not summary["original_native_observed"]
    groups = {}
    for receipt in summary["records"]:
        case = cases[receipt["case_id"]]
        suffix = case["case_id"].split("__")[-1]
        source = REPO / receipt["source_path"]
        positive = REPO / ".runtime-work/c329610-413-saved-fixtures" / (suffix + "-positive")
        negative = REPO / ".runtime-work/c329610-413-saved-fixtures" / (suffix + "-negative")
        native = rows(source / "native_samples.jsonl")
        mapping = rows(source / "video_frames.jsonl")
        trace = rows(source / "trace.jsonl")
        evidence = rows(source / "capture/evidence.jsonl")
        body = rows(source / "body_history.jsonl")
        assert len(native) == len(mapping) == len(trace) == len(evidence) == len(body) == 800
        assert sha(source / "native_samples.jsonl") == receipt["source_native_sha256"]
        assert sha(positive / "analysis-report.json") == receipt["analysis_sha256"]
        assert sha(positive / "result.json") == receipt["result_sha256"]
        assert not (negative / "native_samples.jsonl").exists()
        assert receipt["positive_exit_code"] == 0 and receipt["negative_exit_code"] != 0
        assert all(r["area"] == case["area_classification"] and r["weather"] == "clear" for r in native)
        assert [i for i,r in enumerate(native) if r["course_change"]] == [420]
        onset = next(i for i,r in enumerate(native) if r["signal"] == "left")
        distance = sum(math.dist(native[i-1]["ego_xy_m"], native[i]["ego_xy_m"])
                       for i in range(onset + 1, 421)) / .3048
        assert abs(distance - case["requested_setting"]) < .5
        for i, (n, m, t, e, b) in enumerate(zip(native, mapping, trace, evidence, body)):
            frame = 100 + i
            time = (i + 1) / 20
            assert (n["native_frame"],m["native_frame"],m["carla_frame"],t["frame"],
                    e["original_frame"],b["frame"]) == (frame,) * 6
            assert all(abs(r["time_s"] - time) < 1e-8 for r in (n,m,t,b))
            assert abs(e["recording_time_s"] - time) < 1e-8
            assert {(round(v[0],5),round(v[1],5)) for v in n["native_body_xy_m"]} == {
                (round(v[0],5),round(v[1],5)) for v in e["ego"]["body_vertices_m"]}
        report = json.loads((positive / "analysis-report.json").read_text())
        result = json.loads((positive / "result.json").read_text())
        assert report["original_joins"]["frames"] == 800
        assert result["provenance_kind"] == "synthetic_cpu_fixture"
        assert not result["setup_confirmed"] and not result["behavior_attempted"] and not result["maneuver_completed"]
        assert not result["accepted"] and "synthetic_fixture_not_physical" in result["physical_failure_flags"]
        assert abs(result["measured_values"]["continuous_signal_distance_ft"] - distance) < 1e-8
        assert all(frames == 800 for frames in report["video_frames"].values())
        assert len(report["video_frames"]) == 4
        groups.setdefault(case["area_classification"], []).append((case["requested_setting"], native))
    for items in groups.values():
        assert len(items) == 3
        base = items[0][1]
        for _, native in items[1:]:
            assert [(r["ego_xy_m"],r["heading_deg"],r["course_change"],r["weather"])
                    for r in native] == [(r["ego_xy_m"],r["heading_deg"],r["course_change"],r["weather"])
                                      for r in base]
    print(json.dumps({"saved_cases_audited":6,"frames_each":800,"decoded_videos_each":4,
                      "controlled_groups":2,"selected":False,"original_native_observed":False}))


if __name__ == "__main__":
    main()
