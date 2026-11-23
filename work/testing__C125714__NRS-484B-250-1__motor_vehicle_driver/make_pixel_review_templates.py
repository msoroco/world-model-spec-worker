"""Prepare blank human review packets for original C125714 video frames."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INSTRUCTIONS = {
    "ego": "Identify the ego motor vehicle and its location in an original frame.",
    "other": "Identify the other vehicle at the same crossing in an original frame.",
    "crossing": "Identify the roadway crossing and median opening in original pixels.",
    "device_context": "Review the filmed approach and cite the separate official-device inventory source.",
    "maneuver": "Identify the realized approach and crossing maneuver, including left turn when planned.",
}


def main():
    spec = json.loads((ROOT / "delivery-acceptance.partial.json").read_text())
    for entry in spec["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(ROOT.name + "__")
        if suffix == case:
            raise ValueError("review template case belongs to another assignment")
        packet = {"format": "worker-original-pixel-review", "case_id": case,
                  "diagnostic_fixture": False, "reviewer": None,
                  "video_sha256": None, "frame_map_sha256": None,
                  "core_trace_sha256": None,
                  "observations": {name: {"visible": None, "frame": None,
                                          "view": None, "description": "",
                                          "review_instruction": instruction}
                                   for name, instruction in INSTRUCTIONS.items()},
                  "status": "template_only; original decoded frames and human review required"}
        (ROOT / "independent" / (suffix + "-pixel-review.template.json")).write_text(
            json.dumps(packet, indent=2) + "\n")
    print("Seven incomplete original-pixel review templates prepared")


if __name__ == "__main__":
    main()
