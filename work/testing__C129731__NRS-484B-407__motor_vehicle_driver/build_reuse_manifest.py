"""Build exact selected-reuse CPU command inventory from frozen sources.

The inventory is a review queue, not an execution manifest or ready claim.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ASSIGNMENT = "testing__C129731__NRS-484B-407__motor_vehicle_driver"
SCRIPTS = ("selected_delivery.py", "original_source_acquisition.py",
           "saved_media_decode.py", "selected_media_audit.py",
           "delivery_audit.py", "sight_measurement.py", "comparison_audit.py",
           "selected_pair_review.py", "native_sight_capture.py",
           "carla_sight_adapter.py", "reversal_phase.py",
           "native_sight_cameras.py",
           "native_camera_audit.py",
           "native_case_constructor.py", "reversal_route_controller.py",
           "build_selected_delivery_draft.py",
           "distance_probe_audit.py")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(plan: dict, repository: Path, package: Path) -> dict:
    repository, package = Path(repository), Path(package)
    try:
        package_command = package.resolve().relative_to(repository.resolve())
    except ValueError as exc:
        raise ValueError("package escapes repository") from exc
    if plan.get("assignment_id") != ASSIGNMENT:
        raise ValueError("wrong exact reuse assignment")
    candidates = plan.get("accepted_reuse_candidates", [])
    if len(candidates) != 10 or len({x.get("case_id") for x in candidates}) != 10 or \
            len({x.get("recording_id") for x in candidates}) != 10:
        raise ValueError("ten unique selected candidates required")
    scripts = {name: _sha(package / name) for name in SCRIPTS}
    selected = []
    for row in candidates:
        case_id, recording_id = row["case_id"], row["recording_id"]
        if (not case_id.startswith(ASSIGNMENT + "__") or
                row.get("status") != "source_review_pending" or
                row.get("new_recording_planned") is not False):
            raise ValueError("selected reuse disposition changed")
        sources = [entry for entry in plan.get("sources", [])
                   if Path(entry.get("path", "")).parts[-3:] ==
                   ("accepted", recording_id, "metadata.json")]
        if len(sources) != 1:
            raise ValueError("selected frozen metadata source missing")
        rel = Path(sources[0]["path"])
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("selected metadata path escapes repository")
        raw = repository / rel
        if _sha(raw) != sources[0]["sha256"]:
            raise ValueError("selected frozen metadata hash mismatch")
        meta = json.loads(raw.read_text())
        if (meta.get("case_id") != case_id or meta.get("recording_id") != recording_id or
                meta.get("status") != "accepted" or meta.get("frames") != 900):
            raise ValueError("selected frozen metadata identity mismatch")
        selected.append({"case_id": case_id, "recording_id": recording_id,
                         "metadata_path": str(rel), "metadata_sha256": sources[0]["sha256"],
                         "video_sha256": meta["video_sha256"],
                         "trace_sha256": meta["trace_sha256"],
                         "source_review": "pending",
                         "selected_delivery_script": "selected_delivery.py",
                         "command_template": [
                             ".venv-cpu/bin/python", str(package_command / "selected_delivery.py"),
                             "--plan", str(package_command / "case-plan.json"),
                             "--repository", ".", "--case", case_id,
                             "--recording", recording_id,
                             "--sight-attempt", "{original_sight_attempt}",
                             "--source-bundle", "{scratch_source_bundle}",
                             "--decode-receipt", "{scratch_decode_receipt}",
                             "--review-output", "{scratch_review_output}"],
                         "required_scratch_inputs": ["original_sight_attempt"],
                         "required_original_sources": ["raw.mkv", "trace.json",
                                                       "delivery-audit-completed.json"]})
    index = {row["case_id"]: row["recording_id"] for row in selected}
    pairs = []
    for pair in plan.get("accepted_comparisons_pending_original_review", []):
        cases, recordings = pair.get("case_ids", []), pair.get("recording_ids", [])
        if len(cases) != 2 or len(recordings) != 2 or \
                any(index.get(case) != rec for case, rec in zip(cases, recordings)):
            raise ValueError("selected comparison identity mismatch")
        pairs.append({"comparison_id": pair["comparison_id"],
                      "case_ids": cases, "recording_ids": recordings,
                      "source_review": "pending",
                      "audit_script": "selected_pair_review.py",
                      "command_template": [
                          ".venv-cpu/bin/python", str(package_command / "selected_pair_review.py"),
                          "--plan", str(package_command / "case-plan.json"),
                          "--repository", ".",
                          "--comparison", pair["comparison_id"],
                          "--left-attempt", "{left_original_sight_attempt}",
                          "--right-attempt", "{right_original_sight_attempt}",
                          "--left-bundle", "{scratch_left_source_bundle}",
                          "--right-bundle", "{scratch_right_source_bundle}",
                          "--output", "{scratch_comparison_output}"]})
    if len(pairs) != 7 or len({row["comparison_id"] for row in pairs}) != 7:
        raise ValueError("seven exact comparisons required")
    return {"format": "c129731-selected-reuse-review-queue-v1",
            "assignment_id": ASSIGNMENT, "status": "source_review_pending",
            "new_recordings_planned": 0, "selected_delivery_scripts_sha256": scripts,
            "candidates": selected, "comparisons": pairs,
            "canonical_acceptance": "not_performed_here"}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite selected review queue")
    value = build(json.loads(args.plan.read_text()), args.repository, args.package)
    args.output.write_text(json.dumps(value, indent=2) + "\n")


if __name__ == "__main__":
    main()
