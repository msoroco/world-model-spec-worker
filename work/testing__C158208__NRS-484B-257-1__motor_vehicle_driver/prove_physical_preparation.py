"""Create source-bound synthetic CPU fixtures for the pinned physical gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

from build_offline_draft import DIAGNOSTIC_GEOMETRY, HERE, ROOT
from physical_completion import assess
from source_tick_capture import TickCapture


CONTEXT = {name: True for name in (
    "yield_sign_governs_approach", "no_marked_stop_line", "no_near_side_crosswalk",
    "no_sidewalk_derived_crosswalk", "through_highway_confirmed", "no_officer_control",
    "no_signal_control", "viewpoint_reviewed")}
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def body(x: float, y: float) -> list[list[float]]:
    return [[x - 1, y - .5], [x + 1, y - .5], [x + 1, y + .5], [x - 1, y + .5]]


def capture(attempt: Path, *, incomplete: bool) -> None:
    writer = TickCapture(attempt, DIAGNOSTIC_GEOMETRY, CONTEXT)
    xs = (-9, -5, 0, 5, 5 if incomplete else 13)
    for index, x in enumerate(xs):
        y = (-8, -3, 4, 4, 12)[index]
        writer.append({"frame": 400 + index, "time_s": index * .05,
            "ego": {"body_vertices_xy_m": body(x, 5), "velocity_xy_mps": [3, 0]},
            "through_vehicle": {"center_xy_m": [5, y], "body_vertices_xy_m": body(5, y)},
            "visibility_probe": {"source": "native_raycast", "occluded": index == 0,
                                 "origin_xy_m": [x, 5], "target_xy_m": [5, y]},
            "sign_present": True})
    writer.close()


def lifecycle(events: list[str]) -> None:
    if events != EVENTS:
        raise ValueError("saved processing must follow encoder closure and owner release")


def build() -> None:
    manifest_path = HERE / "execution-manifest.draft.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    scratch_root = ROOT / ".runtime-work" / "c158208-physical-fixtures"
    scratch_root.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="proof-", dir=scratch_root))
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        short = case_id.rsplit("__", 1)[-1]
        construction_hash = entry["construction_sha256"]
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            attempt = scratch / (short + "-" + kind)
            attempt.mkdir(parents=True, exist_ok=True)
            if kind != "missing_evidence":
                capture(attempt, incomplete=kind == "incomplete_motion")
            result = assess(attempt, case_id, construction_hash, diagnostic_fixture=True)
            result_path = HERE / ("physical-" + short + "-" + kind + ".json")
            log_path = HERE / ("physical-" + short + "-" + kind + ".log")
            write(result_path, result)
            expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                        "missing_evidence": "unverified"}[kind]
            actual = result["physical_checks"]["maneuver"]["status"]
            if actual != expected:
                raise ValueError(f"{case_id} {kind}: expected {expected}, got {actual}")
            log_path.write_text(f"diagnostic fixture {case_id} {kind}: {actual}; sealed source checked\n",
                                encoding="utf-8")
            fixtures.append({"kind": kind, "command": "prove_physical_preparation.py " + kind,
                             "exit_code": 0, "log": log_path.name, "log_sha256": sha(log_path),
                             "result": result_path.name, "result_sha256": sha(result_path)})
        lifecycle(EVENTS)
        negative_checked = False
        try:
            lifecycle([event for event in EVENTS if event != "owner_released"])
        except ValueError:
            negative_checked = True
        if not negative_checked:
            raise ValueError("missing owner release was accepted")
        life_log = HERE / ("physical-" + short + "-lifecycle.log")
        life_log.write_text("synthetic capture lifecycle: " + ", ".join(EVENTS) +
                            "\nnegative test: missing owner release rejected\n", encoding="utf-8")
        receipt = {"case_id": case_id, "construction_sha256": construction_hash,
                   "provenance_kind": "synthetic_fixture", "fixtures": fixtures,
                   "lifecycle": {"events": EVENTS, "exit_code": 0,
                                 "log": life_log.name, "log_sha256": sha(life_log)}}
        receipt_path = HERE / ("physical-preparation-" + short + ".json")
        write(receipt_path, receipt)
        entry["physical_preparation"] = {"receipt": receipt_path.name, "sha256": sha(receipt_path)}
    write(manifest_path, manifest)
    print("physical synthetic CPU fixtures and lifecycle proofs built for both exact cases")


if __name__ == "__main__":
    build()
