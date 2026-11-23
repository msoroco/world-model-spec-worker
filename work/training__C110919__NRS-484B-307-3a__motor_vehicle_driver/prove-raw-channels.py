"""Exercise 30-second raw-source channel derivation and three rejection paths."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
sys.path.insert(0, str(FOLDER / "native"))
from derive_channels import derive


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def make_source(path: Path, case: str) -> None:
    path.mkdir()
    config = json.loads((FOLDER / "native/config.json").read_text())
    config["case_suffix"] = case
    config["duration_s"] = 30
    config["knobs"]["duration_s"] = 30
    (path / "config.json").write_text(json.dumps(config))
    geometry = {"stop_line_y_m": -14.0, "nearest_crosswalk_y_m": -11.0,
                "lanes": {"approach_right": {"road_id": 1, "lane_id": -1},
                          "destination_right": {"road_id": 2, "lane_id": -1}}}
    (path / "road_geometry.json").write_text(json.dumps(geometry))
    groups = {key: [] for key in ("native_samples.jsonl", "video_frames.jsonl", "trace.jsonl",
                                 "capture/evidence.jsonl", "body_history.jsonl")}
    for index in range(600):
        frame = index + 100
        time_s = (index + 1) / 20
        y = round(-30 + index * .06, 4)
        body_xy = [[-1, y - 2], [1, y - 2], [1, y + 2], [-1, y + 2]]
        vertices = [[x, z, h] for x, z in body_xy for h in (0, 1.5)]
        native = {"native_frame": frame, "time_s": time_s, "native_body_xy_m": body_xy,
                  "speed_mps": 1.2, "signal_state_observed": "Green",
                  "right_arrow_state_observed": "Green", "opposing_signal_state_observed": "Red",
                  "right_arrow_actor_id": 603, "opposing_signal_actor_id": 604,
                  "walker_conflict_occupied": 120 <= index <= 160,
                  "cross_traffic_conflict_occupied": 90 <= index <= 110,
                  "synthetic_native_sample": True}
        groups["native_samples.jsonl"].append(native)
        groups["video_frames.jsonl"].append({"video_frame": index, "native_frame": frame,
                                               "time_s": time_s})
        groups["trace.jsonl"].append({"frame": frame, "time_s": time_s})
        groups["capture/evidence.jsonl"].append({"original_frame": frame,
                                                  "recording_time_s": time_s})
        groups["body_history.jsonl"].append({"frame": frame, "time_s": time_s,
                                              "body_vertices_m": vertices})
    for name, rows in groups.items():
        write_rows(path / name, rows)


def expect_reject(path: Path, expected: str) -> None:
    try:
        derive(path, path.parent / (path.name + "-derived"))
    except ValueError as exc:
        if expected not in str(exc):
            raise AssertionError(f"Expected {expected!r}; got {exc}") from exc
        return
    raise AssertionError(f"Accepted malformed source: {expected}")


def run() -> dict:
    with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work", prefix="c110919-3a-raw-") as tmp:
        base = Path(tmp)
        results = []
        for case in ("witness_1", "witness_2"):
            source = base / case
            make_source(source, case)
            before = {str(p.relative_to(source)): sha(p) for p in source.rglob("*") if p.is_file()}
            output = base / (case + "-channels")
            receipt = derive(source, output)
            after = {str(p.relative_to(source)): sha(p) for p in source.rglob("*") if p.is_file()}
            assert before == after and receipt["frames"] == 600
            assert len(receipt["channel_hashes"]) == 10
            results.append({"case": case, "source_unchanged": True,
                            "frames": 600, "channels": 10,
                            "receipt_sha256": sha(output / "receipt.json")})
        injected = base / "injected"
        shutil.copytree(base / "witness_1", injected)
        (injected / "channels").mkdir()
        (injected / "channels/kin.velocity.jsonl").write_text('{"value":999}\n')
        expect_reject(injected, "Injected fixture channels")
        missing = base / "missing"
        shutil.copytree(base / "witness_1", missing)
        (missing / "native_samples.jsonl").unlink()
        expect_reject(missing, "Missing retained Native source")
        bad_map = base / "bad_map"
        shutil.copytree(base / "witness_1", bad_map)
        lines = (bad_map / "video_frames.jsonl").read_text().splitlines()
        row = json.loads(lines[200]); row["native_frame"] += 1
        lines[200] = json.dumps(row)
        (bad_map / "video_frames.jsonl").write_text("\n".join(lines) + "\n")
        expect_reject(bad_map, "Retained Native frame join")
        bad_cadence = base / "bad_cadence"
        shutil.copytree(base / "witness_1", bad_cadence)
        for name in ("native_samples.jsonl", "video_frames.jsonl", "trace.jsonl",
                     "capture/evidence.jsonl", "body_history.jsonl"):
            path = bad_cadence / name
            records = [json.loads(line) for line in path.read_text().splitlines()]
            if name == "capture/evidence.jsonl":
                records[200]["recording_time_s"] += .01
            else:
                records[200]["time_s"] += .01
            write_rows(path, records)
        expect_reject(bad_cadence, "Retained Native 20 Hz cadence")
    return {"format": "c110919-raw-channel-proof-v1", "positives": results,
            "negatives": ["injected channels", "missing Native samples", "altered frame join",
                          "altered capture cadence"],
            "scope": "synthetic Native-shaped 600-frame CPU source derivation only"}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
