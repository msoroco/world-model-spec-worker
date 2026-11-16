"""Bind the selected crosswalk plan to the channels and cameras actually authored."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "case-plan.json"
MANIFEST = HERE / "execution-manifest.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def main() -> None:
    plan = json.loads(PLAN.read_text())
    base = f"work/{HERE.name}/"
    runner, finalizer = base + "runner.py", base + "finalize.py"
    mapping = {
        "ru.subject": (["native_pedestrian_pose"], "Original Native walker identity and pose are retained per frame; identity as the judged subject requires source review."),
        "st.crosswalk": (["rel.occupies", "kin.position"], "Authored crosswalk geometry and original Native footprint/position are joined; actual marked-highway designation remains for source review."),
        "rel.occupies": (["rel.occupies", "kin.position"], "Original footprint and position are compared with the authored crosswalk halves; legal occupancy remains for source review."),
        "kin.heading": (["kin.heading"], "Original Native pedestrian forward vector is recorded every frame."),
        "kin.position": (["kin.position"], "Original Native pedestrian position is recorded every frame."),
        "ru.pedestrian": (["native_pedestrian_pose"], "The judged walker type is recorded, while other pedestrian presence and right-half practicability remain unverified in crosswalk-context.json and require original-source review."),
    }
    plan["source_observation_mapping"] = {
        term: {"evidence": explanation, "channels": channels,
               "source_refs": [runner, finalizer]}
        for term, (channels, explanation) in mapping.items()
    }
    plan["observations"] = [
        {"name": "kin.position", "unit": "m", "mandatory": True,
         "purpose": "Original pedestrian center and lateral crosswalk position by frame"},
        {"name": "kin.heading", "unit": "unit vector", "mandatory": True,
         "purpose": "Original heading for determining the right half of travel"},
        {"name": "rel.occupies", "unit": "structured", "mandatory": True,
         "purpose": "Original pedestrian footprint joined to authored crosswalk geometry"},
        {"name": "native_pedestrian_pose", "unit": "structured Native rows", "mandatory": True,
         "purpose": "Original walker identity, pose, footprint and controller request"},
        {"name": "camera_frame_join", "unit": "structured frame index", "mandatory": True,
         "purpose": "Four source camera streams joined to original Native frame and time"},
    ]
    plan["camera_plan"] = {
        "profile": "overview1080-capability", "duration_s": 12, "fps": 20,
        "composition": "synchronized_four_view_primary",
        "coverage": [
            {"view": "overview", "subject": "full pedestrian and marked crosswalk path",
             "interval": "full 12 s crossing attempt", "source": "root config fixed world mount; actual pixels unverified"},
            {"view": "approach", "subject": "pedestrian approach and entry edge",
             "interval": "entry through full traversal", "source": "root config approach mount; actual pixels unverified"},
            {"view": "reference_corner", "subject": "footprint relative to left and right crosswalk halves",
             "interval": "full 12 s attempt", "source": "root config corner mount; actual pixels unverified"},
            {"view": "driver_reference", "subject": "pedestrian travel direction and passage space",
             "interval": "full 12 s attempt", "source": "root config pedestrian-relative mount; actual pixels unverified"},
        ],
        "physical_risk": "Prospective mounts only. Original pixels, crosswalk marking, other pedestrians, obstacles and practicability require source review; fallback3 changes overhead camera mount when visibility fails.",
    }
    write(PLAN, plan)
    manifest = json.loads(MANIFEST.read_text())
    manifest["selection_review"]["case_plan_sha256"] = sha(PLAN)
    write(MANIFEST, manifest)
    print(json.dumps({"case_plan_sha256": sha(PLAN), "manifest_sha256": sha(MANIFEST)}, indent=2))


if __name__ == "__main__":
    main()
