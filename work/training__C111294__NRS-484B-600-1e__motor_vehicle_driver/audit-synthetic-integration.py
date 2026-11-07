"""Independent source audit of C111294 synthetic saved and Core receipts."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED = {"below_80_mph": (75.0, "measured_not_above_80_mph"),
            "inside_80_mph": (79.5, "measured_not_above_80_mph"),
            "above_80_mph": (85.0, "measured_above_80_mph")}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    saved = json.loads((HERE / "synthetic-saved-integration.json").read_text())
    core = json.loads((HERE / "synthetic-core-integration.json").read_text())
    assert saved["ready"] is False and core["ready"] is False
    assert not saved["carla_executed"] and not core["carla_executed"]
    assert len(saved["results"]) == len(core["results"]) == 3
    checked = []
    for item in core["results"]:
        suffix = item["case_id"].split("__")[-1]
        target, relation = EXPECTED[suffix]
        attempt = Path(item["core"]["output"]).parent / "attempt"
        source = attempt / "native_samples.jsonl"
        assert source.is_file() and sha(source) == item["source_sha256"]
        samples, trace, evidence, mapping = (rows(attempt / name) for name in
            ("native_samples.jsonl", "trace.jsonl", "capture/evidence.jsonl",
             "video_frames.jsonl"))
        assert len(samples) == len(trace) == len(evidence) == len(mapping) == 480
        assert all(s["native_frame"] == t["frame"] == e["original_frame"] == m["native_frame"]
                   and m["video_frame"] == index
                   and abs(s["time_s"] - t["time_s"]) < 1e-6
                   for index, (s, t, e, m) in enumerate(zip(samples, trace, evidence, mapping)))
        observed = max(math.sqrt(sum(v*v for v in s["ego_velocity_mps"])) / .44704
                       for s in samples)
        assert abs(observed - target) < 1e-6
        report = json.loads((attempt / "analysis-report.json").read_text())
        result = json.loads((attempt / "result.json").read_text())
        assert report["measurements"]["speed_relation"]["value"]["measured_relation"] == relation
        assert abs(result["realized_observables"]["peak_speed_mph"]["value"] - observed) < 1e-6
        assert not result["accepted"] and result["diagnostic_fixture"]
        assert not result["setup_confirmed"] and not result["behavior_attempted"]
        assert item["core"]["converted"] and item["core"]["decoder_checked"]
        video = Path(item["render"]["video"])
        final = item["final_decode"]
        assert final["passed"] and final["frames"] == 480 and final["video_sha256"] == sha(video)
        assert final["mapping_sha256"] == item["render"]["frame_map_sha256"]
        corresponding = next(row for row in saved["results"] if row["case_suffix"] == suffix)
        assert corresponding["relation"] == relation and corresponding["validator_passed"]
        assert len(corresponding["negative_errors"]) == 2
        checked.append({"case_suffix": suffix, "source_sha256": sha(source),
                        "observed_peak_mph": observed,
                        "final_video_sha256": sha(video), "frames": 480,
                        "ready": False})
    print(json.dumps({"passed": True, "cases": checked,
                      "scope": "independent synthetic saved/Core/Lean/video audit only",
                      "native_capture": False, "accepted": False}, sort_keys=True))


if __name__ == "__main__": main()
