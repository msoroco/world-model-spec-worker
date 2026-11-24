"""Exercise exact comparison acceptance rules on measured CPU fixtures."""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from parking_comparison_audit import PAIRS
from parking_finalizer import finalize
from comparison_audit import sha, verify_pair
from installed_binding import bind


def proof(comparison_id: str, installed_saved_root: Path | None = None) -> None:
    first, second, _ = PAIRS[comparison_id]
    sources = []
    receipts = []
    for suffix in (first, second):
        binding = bind(suffix, installed_saved_root) if installed_saved_root else None
        fixture = (Path(binding["source_attempt"]) if binding else
                   REPO / ".runtime-work" / ("c150041-saved-fixture-v8-" + suffix))
        history = fixture / "parking-history.jsonl"
        measured = finalize(fixture / "reviewed-context.json", fixture, suffix,
                            history, sha(history))
        sources.append({"case_id": ROOT.name + "__" + suffix,
                        "diagnostic_fixture": False,
                        "saved_observations": measured})
        receipts.append({"format": "worker-delivery-audit", "passed": True,
                         "case_id": ROOT.name + "__" + suffix,
                         "checks": {name: True for name in (
                             "native_source", "all_participants", "time_join",
                             "full_video_decode", "actual_pixels", "physical_completion")},
                         "source_audit_sha256": sha(ROOT / "parking_delivery_audit.py"),
                         "delivery_auditor_sha256": sha(ROOT / "independent" / "delivery_audit.py"),
                         "receipt_sha256": "diagnostic-only-" + suffix})
    result = verify_pair(comparison_id, *sources, *receipts)
    if not result["passed"] or result["measurement"]["legal_judgment"] != "unresolved":
        raise AssertionError("comparison proof omitted uncertainty")
    changed = copy.deepcopy(receipts)
    changed[1]["checks"].pop("actual_pixels")
    try:
        verify_pair(comparison_id, *sources, *changed)
    except ValueError as error:
        if "acceptance missing" not in str(error):
            raise
    else:
        raise AssertionError("missing original pixels accepted")
    changed = copy.deepcopy(sources)
    changed[1]["saved_observations"]["source_packet_sha256"] = "0" * 64
    try:
        verify_pair(comparison_id, *changed, *receipts)
    except ValueError as error:
        if "source packet differs" not in str(error):
            raise
    else:
        raise AssertionError("different reviewed packet accepted")
    if installed_saved_root:
        print({"comparison_id": comparison_id, "passed": True,
               "source_kind": "synthetic_fixture", "original_capture_reviewed": False,
               "delivery_ready_claimed": False,
               "installed_bindings": [bind(suffix, installed_saved_root)
                                      for suffix in (first, second)]})
    print(comparison_id + ": measured diagnostic positive and missing-pixel/source negatives passed; no original acceptance")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("comparison_id", choices=tuple(PAIRS))
    parser.add_argument("--installed-saved-root", type=Path)
    args = parser.parse_args()
    proof(args.comparison_id, args.installed_saved_root)
