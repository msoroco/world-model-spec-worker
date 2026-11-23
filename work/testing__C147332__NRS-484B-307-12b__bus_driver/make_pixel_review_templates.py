"""Prepare blank human review packets for four original red-X recordings."""
from __future__ import annotations

import json
from pathlib import Path

from independent.delivery_audit import OBSERVATIONS, SUFFIXES, VIEWS

ROOT = Path(__file__).resolve().parent


def main() -> None:
    for suffix in SUFFIXES:
        case_id = ROOT.name + "__" + suffix
        packet = {
            "format": "worker-original-pixel-review", "case_id": case_id,
            "diagnostic_fixture": False, "reviewer": None,
            "video_sha256": None, "frame_map_sha256": None,
            "core_trace_sha256": None,
            "available_views": list(VIEWS),
            "observations": {name: {"visible": None, "frame": None,
                                    "view": None, "description": None}
                             for name in OBSERVATIONS},
            "review_complete": False,
        }
        path = ROOT / "cases" / suffix / "pixel-review.template.json"
        path.write_text(json.dumps(packet, indent=2) + "\n")
        print(case_id + ": blank original-pixel review packet prepared")


if __name__ == "__main__":
    main()
