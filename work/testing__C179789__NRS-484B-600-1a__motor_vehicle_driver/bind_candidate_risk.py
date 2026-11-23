"""Bind a case-specific fallback decision without inventing an alternate site."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "execution-manifest.json"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    cases = manifest["cases"]
    if len(cases) != 7 or len({case["case_id"] for case in cases}) != 7:
        raise ValueError("seven exact cases required")
    for case in cases:
        assessment = case["physical_risk_assessment"]
        if not all(assessment.get(key) for key in ("risk", "failure_trigger", "fallback_decision")):
            raise ValueError("incomplete physical risk assessment: " + case["case_id"])
        if assessment.get("fallback_candidates") != []:
            raise ValueError("unbound fallback candidate: " + case["case_id"])
        case["candidate_risk"] = {
            "status": "none",
            "reason": (assessment["risk"] + " The predeclared failure trigger is " +
                       assessment["failure_trigger"] +
                       " No original Native attempt or reviewed alternate roadway has established "
                       "a specific tested fallback construction; retain the trigger for the "
                       "first physical attempt."),
        }
        case["candidates"] = []
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print("seven case-specific candidate decisions bound; no untested fallbacks declared")


if __name__ == "__main__":
    main()
