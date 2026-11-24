"""Saved-only, source-sealed diagonal crossing measurement.

This consumes an actual attempt's original readbacks. It does not infer legal
compliance or turn diagnostic fixtures into physical evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from crossing_audit import audit_history
from diagonal_crossing import validate_site


ASSIGNMENT = "testing__C111329__NRS-484B-287-1e__pedestrian"
CASE_STATES = {
    ASSIGNMENT + "__permissive_whole_crossing": "permissive",
    ASSIGNMENT + "__prohibitive_whole_crossing": "prohibitive",
    ASSIGNMENT + "__instruction_changes_during_crossing": "change",
}
CAMERAS = ("front", "rear", "left", "right")


def _sealed_json(attempt: Path, reference: dict, name: str):
    if not isinstance(reference, dict) or not isinstance(reference.get("path"), str):
        raise ValueError(f"missing {name} source reference")
    path = attempt / reference["path"]
    resolved = path.resolve()
    if not resolved.is_relative_to(attempt.resolve()) or not resolved.is_file():
        raise ValueError(f"{name} source escapes or is missing")
    digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
    if digest != reference.get("sha256"):
        raise ValueError(f"{name} source hash mismatch")
    return json.loads(resolved.read_text(encoding="utf-8")), digest


def _frame_numbers(rows: list, name: str):
    if not isinstance(rows, list) or len(rows) < 3:
        raise ValueError(f"incomplete {name} history")
    frames = [row.get("original_frame") for row in rows]
    if any(type(frame) is not int for frame in frames):
        raise ValueError(f"invalid {name} frame identity")
    if any(b != a + 1 for a, b in zip(frames, frames[1:])):
        raise ValueError(f"{name} frame gap")
    return frames


def _time_join(rows: list, frames: list[int], name: str):
    for row, frame in zip(rows, frames):
        timestamp = row.get("elapsed_s")
        if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
            raise ValueError(f"missing {name} original timestamp")
        if abs(float(timestamp) - (frame - frames[0]) / 20.0) > 0.001:
            raise ValueError(f"{name} timestamp is not 20 Hz synchronized")


def _case_instruction(kind: str, instructions: list[str]):
    if not instructions:
        raise ValueError("no crossing instruction observed")
    allowed = {"diagonal_walk", "diagonal_dont_walk"}
    if set(instructions) - allowed:
        raise ValueError("unrecognized diagonal instruction")
    if kind == "permissive" and set(instructions) != {"diagonal_walk"}:
        raise ValueError("permissive case instruction mismatch")
    if kind == "prohibitive" and set(instructions) != {"diagonal_dont_walk"}:
        raise ValueError("prohibitive case instruction mismatch")
    if kind == "change" and not (instructions[0] == "diagonal_walk" and
                                  "diagonal_dont_walk" in instructions[1:]):
        raise ValueError("phase-change case instruction mismatch")


def process_saved(attempt_dir: str | Path, case_id: str, output: str | Path,
                  *, allow_diagnostic: bool = False):
    """Verify joins and write measured summary; raises on absent original data."""
    if case_id not in CASE_STATES:
        raise ValueError("unassigned diagonal case")
    attempt = Path(attempt_dir).resolve()
    if not attempt.is_dir():
        raise ValueError("attempt directory missing")
    manifest_path = attempt / "acquisition.json"
    if not manifest_path.is_file():
        raise ValueError("acquisition receipt missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("assignment_id") != ASSIGNMENT or manifest.get("case_id") != case_id:
        raise ValueError("acquisition assignment/case mismatch")
    if manifest.get("diagnostic") is not False and not allow_diagnostic:
        raise ValueError("diagnostic or unconfirmed acquisition rejected")
    if manifest.get("fps") != 20 or manifest.get("camera_ids") != list(CAMERAS):
        raise ValueError("20 Hz four-camera acquisition contract missing")
    site, site_hash = _sealed_json(attempt, manifest.get("site"), "site")
    plan = validate_site(site, attempt)
    walker, walker_hash = _sealed_json(attempt, manifest.get("walker"), "walker")
    device, device_hash = _sealed_json(attempt, manifest.get("device"), "device")
    cameras, cameras_hash = _sealed_json(attempt, manifest.get("camera_frames"), "camera frames")
    footprint, footprint_hash = _sealed_json(attempt, manifest.get("crossing_polygon"), "crossing polygon")
    frames = _frame_numbers(walker, "walker")
    if _frame_numbers(device, "device") != frames or _frame_numbers(cameras, "camera") != frames:
        raise ValueError("source frame identities differ")
    for rows, name in ((walker, "walker"), (device, "device"), (cameras, "camera")):
        _time_join(rows, frames, name)
    device_inventory_hash = plan["source_sha256"]["device_inventory"]
    for row in device:
        if row.get("source_sha256") != device_inventory_hash:
            raise ValueError("device readback is not bound to inventoried source")
    for row in cameras:
        readings = row.get("cameras")
        if not isinstance(readings, dict) or set(readings) != set(CAMERAS):
            raise ValueError("four synchronized camera readbacks required")
        if any(type(readings[c]) is not int or readings[c] != row["original_frame"] for c in CAMERAS):
            raise ValueError("camera original-frame readback mismatch")
    measured = audit_history(plan, footprint, walker, device)
    _case_instruction(CASE_STATES[case_id], measured["observed_instructions"])
    result = {"assignment_id": ASSIGNMENT, "case_id": case_id,
              "measurement": measured, "fps": 20, "original_frames": len(frames),
              "camera_ids": list(CAMERAS), "diagnostic": bool(manifest.get("diagnostic")),
              "source_sha256": {"site": site_hash, "walker": walker_hash,
                                "device": device_hash, "camera_frames": cameras_hash,
                                "crossing_polygon": footprint_hash},
              "full_video_decode": False, "actual_pixels_verified": False,
              "physical_completion_verified": False, "legal_conclusion": "not_assessed"}
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def audit_saved_comparison(reference: dict, variant: dict, *, allow_diagnostic: bool = False):
    """Compare separately captured cases while holding observable controls fixed."""
    cases = (reference.get("case_id"), variant.get("case_id"))
    if cases not in ((ASSIGNMENT + "__permissive_whole_crossing",
                     ASSIGNMENT + "__prohibitive_whole_crossing"),
                    (ASSIGNMENT + "__permissive_whole_crossing",
                     ASSIGNMENT + "__instruction_changes_during_crossing")):
        raise ValueError("undeclared diagonal comparison")
    if (reference.get("diagnostic") or variant.get("diagnostic")) and not allow_diagnostic:
        raise ValueError("diagnostic comparison rejected")
    for key in ("fps", "original_frames", "camera_ids"):
        if reference.get(key) != variant.get(key):
            raise ValueError(f"comparison acquisition contract changed: {key}")
    if reference.get("fps") != 20 or reference.get("camera_ids") != list(CAMERAS):
        raise ValueError("incomplete camera/time contract")
    if reference.get("source_sha256", {}).get("site") != variant.get("source_sha256", {}).get("site"):
        raise ValueError("comparison site changed")
    a = reference.get("measurement", {})
    b = variant.get("measurement", {})
    for key in ("device_id", "source_sha256", "exception_484b_290_review", "crossing_frames"):
        if a.get(key) != b.get(key):
            raise ValueError(f"fixed comparison condition changed: {key}")
    if not a.get("all_crossing_frames_permissive") or b.get("all_crossing_frames_permissive"):
        raise ValueError("instruction contrast unobserved")
    if cases[1].endswith("instruction_changes_during_crossing") and (
        not b.get("observed_instructions") or b["observed_instructions"][0] != "diagonal_walk"
        or "diagonal_dont_walk" not in b["observed_instructions"][1:]
    ):
        raise ValueError("phase change unobserved")
    return {"reference_case_id": cases[0], "variant_case_id": cases[1],
            "comparison_verified": True, "legal_conclusion": "not_assessed"}
