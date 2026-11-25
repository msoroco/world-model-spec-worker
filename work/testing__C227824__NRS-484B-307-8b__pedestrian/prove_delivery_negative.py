"""Show independent Native delivery audit rejects all diagnostic attempts."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

from build_construction import ROOT
from delivery_audit import audit


REPO = ROOT.parents[1]
SOURCE = REPO / ".runtime-work" / "c227824-saved-processing-v1"
PRIVATE = REPO / ".runtime-work" / "c227824-delivery-negative"


def main():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in json.loads((ROOT / "case-plan.json").read_text())["cases"]:
        case_id = case["case_id"]
        suffix = case_id[len(ROOT.name) + 2:]
        attempt = SOURCE / suffix / "attempt"
        try:
            audit(attempt)
        except ValueError as error:
            if "missing or unsafe sealed source: capture-seal.json" not in str(error):
                raise
        else:
            raise ValueError("synthetic attempt passed production Native audit")
        corrupt = PRIVATE / suffix
        if corrupt.exists():
            shutil.rmtree(corrupt)
        shutil.copytree(attempt, corrupt)
        (corrupt / "capture-seal.json").write_text(json.dumps({
            "format": "worker-sealed-capture", "provenance_kind": "native",
            "diagnostic_fixture": True, "restoration": {"restored": True},
            "events": ["capture_finished", "encoders_closed", "restoration_verified"]}) + "\n")
        try:
            audit(corrupt)
        except ValueError as error:
            if "Native capture seal or restoration invalid" not in str(error):
                raise
        else:
            raise ValueError("diagnostic marker passed production Native audit")
        rows.append({"case_id": case_id, "missing_native_seal_rejected": True,
                     "diagnostic_seal_rejected": True})
    print(json.dumps({"format": "c227824-production-delivery-negative-summary",
                      "cases": rows, "physical_acceptance_claimed": False}, indent=2))


if __name__ == "__main__":
    main()
