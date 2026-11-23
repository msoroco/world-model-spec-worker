"""Create incomplete original-pixel review packets for operator completion."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
OBSERVATIONS = {
    "taxi": "Identify the same licensed cab throughout the stand departure and junction maneuver.",
    "stand_marking": "Identify the physical stand marking and the cab's departure location.",
    "posted_notice": "Read the posted right-turn notice in an original camera frame.",
    "first_intersection": "Identify the first street intersection after stand departure.",
    "maneuver": "Identify the cab's turn or straight movement through that first intersection.",
}


def main() -> None:
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.removeprefix(ROOT.name + "__")
        if suffix == case_id:
            raise ValueError("pixel review template selected another assignment")
        template = {
            "format": "worker-original-pixel-review", "case_id": case_id,
            "reviewer": None, "diagnostic_fixture": False,
            "video_sha256": None, "frame_map_sha256": None, "core_trace_sha256": None,
            "available_views": list(VIEWS),
            "observations": {key: {"visible": None, "frame": None, "view": None,
                                   "description": "", "review_instruction": instruction}
                             for key, instruction in OBSERVATIONS.items()},
            "status": "template_only; original decoded frames and review required",
        }
        path = ROOT / "cases" / suffix / "pixel-review.template.json"
        path.write_text(json.dumps(template, indent=2) + "\n")
    print("Incomplete original-pixel review templates prepared for " +
          ", ".join(entry["case_id"] for entry in manifest["cases"]))


if __name__ == "__main__":
    main()
