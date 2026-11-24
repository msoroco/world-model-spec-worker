"""Exercise saved-source positive/negative paths in ignored .runtime-work scratch."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "native"))
from authorization import requested
from saved_finalizer import finalize


def write_case(folder: Path, case: str) -> dict[str, str]:
    folder.mkdir()
    rows = requested(case)
    person = []
    device = []
    display = "diagonal_walk_requested" if case == "probe_01" else "no_diagonal_permission"
    for row in rows:
        person.append({"frame": row["frame"], "time_s": row["time_s"],
                       "pedestrian_xy_m": row["pedestrian_xy_m"],
                       "footprint_xy_m": row["footprint_xy_m"],
                       "source_kind": "synthetic_native_sample"})
        device.append({"frame": row["frame"], "time_s": row["time_s"],
                       "device_id": row["device_id"], "display_code": display,
                       "official_status": "unverified", "source_kind": "synthetic_native_sample"})
    files = {"pedestrian.jsonl": ("\n".join(json.dumps(x, separators=(",", ":")) for x in person)+"\n").encode(),
             "device.jsonl": ("\n".join(json.dumps(x, separators=(",", ":")) for x in device)+"\n").encode(),
             "map.json": json.dumps({"source_kind": "synthetic_native_sample",
                                     "intersection_bounds_xy_m": [-5, -5, 5, 5],
                                     "device_id": "c109166-planned-diagonal-head",
                                     "official_status": "unverified",
                                     "exception_484b290": "unresolved"},
                                    sort_keys=True).encode()}
    for name, raw in files.items():
        (folder / name).write_bytes(raw)
    return {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()}


def rejected(folder: Path, hashes: dict[str, str], case: str, phrase: str) -> None:
    try:
        finalize(folder, hashes, case)
    except ValueError as error:
        assert phrase in str(error), (phrase, error)
    else:
        raise AssertionError("bad saved input accepted: " + phrase)


def mutate_jsonl(path: Path, frame: int, key: str, value: object) -> None:
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[frame][key] = value
    path.write_text("\n".join(json.dumps(x, separators=(",", ":")) for x in rows)+"\n")


def main() -> None:
    scratch = Path(os.environ["TMPDIR"]).resolve()
    if ".runtime-work" not in scratch.parts:
        raise ValueError("TMPDIR must be under .runtime-work")
    with tempfile.TemporaryDirectory(dir=scratch) as temp:
        root = Path(temp)
        reports = {}
        for case in ("probe_01", "probe_02"):
            folder = root / case
            hashes = write_case(folder, case)
            report = finalize(folder, hashes, case)
            assert report["frames"] == 600 and report["duration_s"] == 30
            assert 16.9 < report["path_length_m"] < 17.1
            reports[case] = report
        assert reports["probe_01"]["intersection_entry_frame"] == reports["probe_02"]["intersection_entry_frame"]
        assert reports["probe_01"]["intersection_exit_frame"] == reports["probe_02"]["intersection_exit_frame"]
        assert reports["probe_01"]["path_length_m"] == reports["probe_02"]["path_length_m"]
        assert reports["probe_01"]["source_sha256"]["pedestrian.jsonl"] == reports["probe_02"]["source_sha256"]["pedestrian.jsonl"]
        folder = root / "probe_02"
        hashes = reports["probe_02"]["source_sha256"]
        (folder / "map.json").unlink()
        rejected(folder, hashes, "probe_02", "required saved source missing")
        write_case_folder = root / "negative"
        fresh = write_case(write_case_folder, "probe_02")
        mutate_jsonl(write_case_folder / "device.jsonl", 150, "display_code", "diagonal_walk_requested")
        rejected(write_case_folder, fresh, "probe_02", "source hash mismatch")
        fresh["device.jsonl"] = hashlib.sha256((write_case_folder / "device.jsonl").read_bytes()).hexdigest()
        rejected(write_case_folder, fresh, "probe_02", "device state differs")
        mutate_jsonl(write_case_folder / "device.jsonl", 150, "official_status", "official")
        fresh["device.jsonl"] = hashlib.sha256((write_case_folder / "device.jsonl").read_bytes()).hexdigest()
        rejected(write_case_folder, fresh, "probe_02", "authority overstated")
        mutate_jsonl(write_case_folder / "pedestrian.jsonl", 100, "frame", 101)
        fresh["pedestrian.jsonl"] = hashlib.sha256((write_case_folder / "pedestrian.jsonl").read_bytes()).hexdigest()
        rejected(write_case_folder, fresh, "probe_02", "frame/time join")
        print(json.dumps({"format": "c109166-saved-finalizer-cpu-proof-v1",
                          "passed": True, "cases": [reports[c] for c in ("probe_01", "probe_02")],
                          "negative_source_probes": 5,
                          "fixture_source_kind": "synthetic_native_sample",
                          "original_native_or_legal_result": None}, sort_keys=True))


if __name__ == "__main__":
    main()
