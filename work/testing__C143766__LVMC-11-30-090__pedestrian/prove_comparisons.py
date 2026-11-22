"""Reopen both original diagnostic sources for the two selected pairs."""
from __future__ import annotations

import json
from pathlib import Path

from comparison_audit import audit_pair


def prove(root):
    root = Path(root)
    def source(band):
        return root / "cases" / (band + "_walk") / "diagnostic-source-manifest.json"
    return {"format": "c143766-diagnostic-saved-comparisons-v1",
            "pairs": {name: audit_pair(root, source("roadway"), source(band),
                                       declared_band_change=True)
                      for name, band in (("roadway_vs_sidewalk", "sidewalk"),
                                         ("roadway_vs_shoulder", "shoulder"))},
            "limitations": "Generated original-shaped histories only; not Native capture or legal/physical acceptance."}


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    (root / "diagnostic-comparison-proof.json").write_text(json.dumps(prove(root), indent=2) + "\n")
