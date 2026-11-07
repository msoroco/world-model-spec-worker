"""Independent audit of saved Native, Core, Lean and video CPU fixtures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED = {"probe_a": "measured_early_decrease_held",
            "probe_b": "measured_no_material_decrease"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    saved = json.loads((HERE / "synthetic-saved-integration.json").read_text())
    core = json.loads((HERE / "synthetic-core-integration.json").read_text())
    assert saved["format"] == "c111294-603-synthetic-saved-integration-v1"
    assert core["format"] == "c111294-603-synthetic-core-integration-v1"
    assert len(saved["results"]) == len(core["results"]) == 2
    assert not saved["ready"] and not core["ready"]
    assert not saved["carla_executed"] and not core["carla_executed"]
    seen = set()
    for item in core["results"]:
        suffix = item["case_id"].split("__")[-1]
        assert suffix in EXPECTED and suffix not in seen
        seen.add(suffix)
        attempt = Path(item["core"]["output"]).parent / "attempt"
        source = attempt / "native_samples.jsonl"
        assert sha(source) == item["source_sha256"]
        samples, trace, evidence, mapping, body, capture = (
            rows(attempt / name) for name in
            ("native_samples.jsonl", "trace.jsonl", "capture/evidence.jsonl",
             "video_frames.jsonl", "body_history.jsonl", "capture/native/frames.jsonl"))
        assert len(samples) == len(trace) == len(evidence) == len(mapping) == len(body) == len(capture) == 480
        for index, (s, t, e, m, b, c) in enumerate(zip(samples, trace, evidence, mapping, body, capture)):
            assert s["native_frame"] == t["frame"] == e["original_frame"] == m["native_frame"] == b["frame"] == c["frame"]
            assert m["video_frame"] == index
            assert abs(s["time_s"] - t["time_s"]) < 1e-6
        report = json.loads((attempt / "analysis-report.json").read_text())
        result = json.loads((attempt / "result.json").read_text())
        assert report["measurements"]["intersection_approach"]["value"]["measured_relation"] == EXPECTED[suffix]
        assert report["original_joins"]["frames"] == 480
        assert set(report["video_frames"].values()) == {480}
        assert result["diagnostic_fixture"] and not result["accepted"]
        assert not result["setup_confirmed"] and not result["behavior_attempted"]
        assert item["core"]["converted"] and item["core"]["decoder_checked"]
        video = Path(item["render"]["video"])
        final = item["final_decode"]
        assert final["passed"] and final["frames"] == 480
        assert final["video_sha256"] == sha(video)
        assert final["mapping_sha256"] == item["render"]["frame_map_sha256"]
        saved_item = next(row for row in saved["results"] if row["case_suffix"] == suffix)
        assert saved_item["relation"] == EXPECTED[suffix]
        assert saved_item["analysis_sha256"] == sha(attempt / "analysis-report.json")
        assert saved_item["result_sha256"] == sha(attempt / "result.json")
        assert saved_item["validator_passed"] and saved_item["source_preserved"]
        assert len(saved_item["negative_errors"]) == 2
    assert seen == set(EXPECTED)
    print(json.dumps({"passed": True, "cases": sorted(seen), "frames_per_case": 480,
                      "scope": "independent synthetic CPU integration audit",
                      "carla_executed": False, "accepted": False, "ready": False}, sort_keys=True))


if __name__ == "__main__":
    main()
