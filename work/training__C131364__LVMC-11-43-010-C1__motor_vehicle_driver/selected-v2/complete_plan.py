"""Add exact four-view capture and source-term mapping to the owned plan."""

import json
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "case-plan.json"
plan = json.loads(path.read_text())
plan["camera_plan"] = {
    "profile": "overview1080-capability",
    "duration_s": 30,
    "composition": "synchronized_four_view_primary",
    "coverage": [
        {"view": "overview", "subject": "full roundabout, ego and exit approach", "interval": "all 600 frames"},
        {"view": "approach", "subject": "ego entry, circulating path and exit", "interval": "all 600 frames"},
        {"view": "reference_corner", "subject": "lane adjacency and intended exit context", "interval": "all 600 frames"},
        {"view": "driver_reference", "subject": "ego lane occupancy and exit direction", "interval": "all 600 frames"},
    ],
    "original_pixel_review_required": True,
}
assignment_path = ROOT.parents[1] / "inputs" / ROOT.name / "assignment.json"
assignment = json.loads(assignment_path.read_text())
source = {"path": f"inputs/{ROOT.name}/assignment.json",
          "sha256": hashlib.sha256(assignment_path.read_bytes()).hexdigest()}
mapping = {}
for item in assignment["source_observation_terms"]:
    term = item["term"]
    if term == "drv.u_turn":
        mapping[term] = {
            "evidence": "This fixed left-turn cell cannot realize a U-turn; exact-law C131055 needs separate binding and original review.",
            "channels": [], "source_refs": [source],
        }
    else:
        mapping[term] = {
            "evidence": "Original Native route/map readback and synchronized camera pixels require independent physical review; CPU authored route is a request only.",
            "channels": ["roundabout_route"], "source_refs": [source],
        }
plan["source_observation_mapping"] = mapping
plan["requirement_dispositions"][0]["evidence_or_gap"] = (
    "Two exact source-hashed 600-frame/four-camera selected left-turn CPU cases, each with "
    "paired fallback, pass offline, public compatibility, and saved-only processing. "
    "Original Native geometry, pixels, lane occupancy, actual left-turn exit and legal "
    "interpretation remain unverified; U-turn is handed to exact-law C131055."
)
path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
