"""Recheck seven exact diagnostic acceptance contracts with pinned runtime."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
output = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "/")).resolve()
if not output.is_relative_to(REPO / ".runtime-work"):
    raise ValueError("set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.path.insert(0, str(REPO / "runtime"))
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case


def main() -> None:
    packet = json.loads((ROOT / "delivery-acceptance.partial.json").read_text())
    if packet.get("original_capture_reviewed") is not False or len(packet.get("cases", [])) != 7:
        raise ValueError("expected seven diagnostic-only contracts")
    for receipt in packet["cases"]:
        validate_case(ROOT, {"case_id": receipt["case_id"],
                             "delivery_acceptance": receipt}, {"full-test"})
    print("seven exact pinned delivery contracts pass; diagnostic only")


if __name__ == "__main__":
    main()
