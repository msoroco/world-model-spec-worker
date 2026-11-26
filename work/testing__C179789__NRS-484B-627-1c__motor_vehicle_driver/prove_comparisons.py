"""Audit five exact diagnostic route contrasts and stale source rejection."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile

from comparison_audit import audit

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PRIVATE = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()


def main() -> None:
    if not PRIVATE.is_relative_to(REPO / ".runtime-work"):
        raise ValueError("comparison scratch must be under .runtime-work")
    plan = json.loads((ROOT / "case-plan.json").read_text())
    receipts = []
    for comparison in plan["comparisons"]:
        ident = comparison["comparison_id"]
        paths = [PRIVATE / ("saved-compat-" + case.rsplit("__", 1)[-1] + "-v1")
                 for case in comparison["case_ids"]]
        proof = audit(ident, paths, diagnostic_fixture=True)
        if proof.get("software_measurement_passed") is not True:
            raise ValueError("route comparison measurement missing: " + ident)
        with tempfile.TemporaryDirectory(prefix="comparison-stale-", dir=PRIVATE) as temporary:
            stale = Path(temporary) / "attempt"
            shutil.copytree(paths[0], stale)
            (stale / "original-site.json").write_text("{}\n")
            try:
                audit(ident, [stale, *paths[1:]], diagnostic_fixture=True)
            except ValueError as error:
                if "route site hash differs" not in str(error):
                    raise
            else:
                raise AssertionError("stale route comparison source accepted")
        receipts.append({**proof, "stale_original_site_rejected": True})
        print(ident, flush=True)
    (ROOT / "comparison-audit-receipts.json").write_text(
        json.dumps(receipts, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
