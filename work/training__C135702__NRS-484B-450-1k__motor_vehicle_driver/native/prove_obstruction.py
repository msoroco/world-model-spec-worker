"""Source-shaped CPU proof for saved obstruction measurement; synthetic only."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from measure_obstruction import measure, sha256


def _row(index: int, obstructed: bool) -> dict:
    return {
        "native_frame": index,
        "time_s": index / 20,
        "road_xy_m": [-100.0, -3.5, 100.0, 3.5],
        "obstruction_xy_m": [0.0, 1.0, 5.0, 3.4],
        "obstruction_kind": "excavation",
        "ego_body_xy_m": [0.1, -3.4, 4.9, 0.5 if obstructed else -1.2],
        "ego_speed_m_s": 0.0,
        "passing_body_xy_m": [-6.0 + index * 0.01, -0.8, -2.0 + index * 0.01, 0.8],
        "passing_speed_m_s": 0.0 if obstructed else 3.0,
        "exceptions": {"traffic_conflict": False, "law_direction": False,
                       "police_direction": False, "traffic_device": False},
        "exception_source": {"traffic_conflict_reviewed": True,
                             "law_direction_reviewed": True,
                             "police_direction_reviewed": True,
                             "traffic_device_reviewed": True},
    }


def _write(path: Path, rows: list[dict]) -> str:
    path.write_text("".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows))
    return sha256(path)


def _reject(path: Path, expected_hash: str, phrase: str) -> None:
    try:
        measure(path, expected_hash)
    except ValueError as error:
        if phrase in str(error):
            return
        raise AssertionError(f"Wrong rejection: {error}") from error
    raise AssertionError("Damaged source was accepted")


def main() -> None:
    with TemporaryDirectory(prefix="c135702-obstruction-") as temp:
        root = Path(temp)
        results = {}
        for name, obstructed in (("narrow_gap_halt", True), ("clear_gap_pass", False)):
            rows = [_row(index, obstructed) for index in range(600)]
            path = root / (name + ".jsonl")
            source_hash = _write(path, rows)
            result = measure(path, source_hash)
            assert result["frames"] == 600 and result["parked_alongside_frames"] == 600
            assert result["exception_flags_all_false"] and not result["physical_cause_confirmed"]
            assert result["legal_obstruction_verdict"] == "unresolved_requires_review"
            assert result["passing_halt_frames"] == (600 if obstructed else 0)
            results[name] = {"source_sha256": source_hash, "measurement": result}
        assert results["narrow_gap_halt"]["measurement"]["minimum_open_width_m"] < results["clear_gap_pass"]["measurement"]["minimum_open_width_m"]
        damaged = [_row(index, True) for index in range(600)]
        damaged[300]["exceptions"].pop("traffic_device")
        path = root / "damaged.jsonl"
        source_hash = _write(path, damaged)
        _reject(path, source_hash, "Exception flags incomplete")
        damaged[300] = _row(300, True)
        damaged[301]["exception_source"]["police_direction_reviewed"] = False
        source_hash = _write(path, damaged)
        _reject(path, source_hash, "Exception source review incomplete")
        damaged[301] = _row(301, True)
        source_hash = _write(path, damaged)
        _reject(path, "0" * 64, "Original Native source hash differs")
        path.unlink()
        _reject(path, source_hash, "Missing required source")
        print(json.dumps({"format": "c135702-obstruction-cpu-proof-v1", "results": results,
                          "negative_rejections": 4, "scope": "synthetic saved samples only"}, sort_keys=True))


if __name__ == "__main__":
    main()
