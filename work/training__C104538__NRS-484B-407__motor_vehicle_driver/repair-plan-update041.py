"""Align the exact visibility sweep plan with recorded channels and cameras."""
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
    explanations = {
        "drv.u_turn": "Original Native heading and body trajectory establish reversal at the judged point; realized motion remains unverified.",
        "st.curvature": "Authored road curve and original Native position are joined; loaded Native geometry requires source verification.",
        "st.grade": "Authored grade profile and original Native position are joined; loaded Native crest geometry requires source verification.",
        "st.sight_distance": "Original approaching-driver eye/body poses and sightline rays are retained in both directions; actual pixel visibility requires independent review.",
        "rel.oncoming": "Original approaching actor body and lane direction are retained for both approach directions.",
        "drv.approaching": "Original approaching actor position and direction are retained through the 500-foot interval.",
        "kin.position": "Original ego position at reversal is retained per Native frame.",
    }
    plan["source_observation_mapping"] = {
        term: {"evidence": detail, "channels": [term],
               "source_refs": [base + "runner.py", base + "measure_native.py", base + "finalize.py"]}
        for term, detail in explanations.items()
    }
    units = {"st.sight_distance": "ft, structured", "kin.position": "m, structured"}
    plan["observations"] = [
        {"name": name, "unit": units.get(name, "structured"), "mandatory": True,
         "purpose": detail}
        for name, detail in {**explanations,
                             "st.crest": "Original position relative to authored crest geometry; loaded Native geometry remains for review."}.items()
    ]
    plan["camera_plan"] = {
        "profile": "overview1080-capability", "duration_s": 24, "fps": 20,
        "composition": "synchronized_four_view_primary",
        "coverage": [
            {"view": "overview", "subject": "full vehicle reversal and curve/crest context",
             "interval": "entire 24 s approach and U-turn", "source": "root config fixed overview mount; actual pixels unverified"},
            {"view": "approach", "subject": "first approaching driver's eye and complete vehicle body",
             "interval": "500-foot approach through judged reversal", "source": "root config approach mount; actual pixels unverified"},
            {"view": "reference_corner", "subject": "opposite approach and sightline to vehicle body",
             "interval": "500-foot opposite approach through judged reversal", "source": "root config corner mount; actual pixels unverified"},
            {"view": "driver_reference", "subject": "driver direction view of road, crest and opposing traffic",
             "interval": "entire 24 s interval", "source": "root config ego mount; actual pixels unverified"},
        ],
        "physical_risk": "Prospective camera mounts only. Native curve/crest, actual reversal, two-direction driver-eye/body visibility at 500 feet and source pixels require independent local review.",
    }
    write(PLAN, plan)
    manifest = json.loads(MANIFEST.read_text())
    manifest["selection_review"]["law_input_sha256"] = sha(Path("inputs") / HERE.name / "assignment.json")
    manifest["selection_review"]["case_plan_sha256"] = sha(PLAN)
    write(MANIFEST, manifest)
    print(json.dumps({"case_plan_sha256": sha(PLAN),
                      "manifest_sha256": sha(MANIFEST)}, indent=2))


if __name__ == "__main__":
    main()
