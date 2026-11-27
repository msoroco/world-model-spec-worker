"""Create an exact draft manifest for CPU construction and proof binding."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / "case-plan.json").read_text())
ASSIGNMENT = PLAN["assignment_id"]


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    entries = []
    for row in PLAN["cases"]:
        variant = row["variant"]
        primary = ROOT / "cases" / variant / "construction.json"
        fallback = ROOT / "cases" / variant / "fallback1" / "construction.json"
        entries.append({
            "case_id": row["case_id"], "kind": "delivery",
            "construction": str(primary.relative_to(ROOT)),
            "construction_sha256": _sha(primary),
            "candidate_risk": row["candidate_risk"],
            "candidates": [{
                "id": "fallback1", "construction": str(fallback.relative_to(ROOT)),
                "construction_sha256": _sha(fallback),
                "changed_knobs": ["reverse the surveyed alley approach while retaining the exact loading target and actor schedules"],
                "trigger": {"source": "original Native body and four-camera history",
                            "metric": "vehicle halt, actor contact and complete camera coverage",
                            "failure_condition": "primary approach cannot realize the original halt, actor contact or complete views"},
            }],
            "measurement_procedure": {"entrypoint": "alley_activity.py",
                                      "method": "source-sealed original passenger, goods, driver and vehicle activity"},
        })
    runtime_source = Path(__file__).resolve().parents[2] / "runtime/SOURCE-MANIFEST.json"
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": _sha(runtime_source), "cases": entries}
    (ROOT / "execution-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    build()
