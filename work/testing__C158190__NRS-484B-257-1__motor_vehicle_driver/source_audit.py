"""Check the immutable inputs needed to construct the exact yield branch."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from yield_view_measurement import ASSIGNMENT


REQUIRED_ORIGINAL = ("yield_sign_and_governing_approach", "ego_route_survey",
                     "line_crosswalk_sidewalk_survey",
                     "nearest_view_ray_survey", "through_highway_route_and_motion")


def audit(repo: Path) -> dict:
    source = repo / "inputs" / ASSIGNMENT
    assignment_path = source / "assignment.json"
    assignment = json.loads(assignment_path.read_text())
    if assignment.get("assignment_id") != ASSIGNMENT:
        raise ValueError("frozen assignment identity changed")
    cell = assignment.get("cell", {})
    if cell.get("cell_id") != "C158190":
        raise ValueError("frozen cell identity changed")
    accepted = sorted((source / "accepted").glob("*/metadata.json"))
    original_files = sorted(path for path in source.rglob("*") if path.is_file()
                            and path.name in {"trace.json", "video.webm", "yield-site.json",
                                              "ego-route-survey.json",
                                              "marking-survey.json", "view-ray-survey.json",
                                              "through-highway-survey.json"})
    required_names = {"yield_sign_and_governing_approach": "yield-site.json",
                      "ego_route_survey": "ego-route-survey.json",
                      "line_crosswalk_sidewalk_survey": "marking-survey.json",
                      "nearest_view_ray_survey": "view-ray-survey.json",
                      "through_highway_route_and_motion": "through-highway-survey.json"}
    present_names = {path.name for path in original_files}
    return {"assignment_id": ASSIGNMENT,
            "assignment_sha256": hashlib.sha256(assignment_path.read_bytes()).hexdigest(),
            "frozen_cell_control": cell.get("control"),
            "accepted_metadata_count": len(accepted),
            "accepted_original_file_count": len(original_files),
            "original_paths": [str(path.relative_to(repo)) for path in original_files],
            "missing_source_classes": [name for name in REQUIRED_ORIGINAL
                                       if required_names[name] not in present_names],
            "source_limit": ("A stop-sign catalog annotation is not an original yield-sign readback. "
                             "Accepted metadata and authored review context do not contain the original "
                             "site surveys, trace, or video needed to prove this selected branch.")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.repo.resolve()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
