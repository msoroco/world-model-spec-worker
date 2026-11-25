"""Check a proposed original pedestrian site before a Native GPU attempt.

This checks source bindings and the device inventory's applicability statement.
It does not decide whether crossing is legally permitted or physically possible.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from native_crossing import SourceError, source, verify_site


DEVICE_LAWS = {f"NRS-484B-283-1d{part}" for part in range(1, 5)}
CASE_PROVISIONS = {
    'other_device_stop': {'NRS-484B-283-1d4'},
    'other_device_cross': {'NRS-484B-283-1d4'},
    'walk_cross': {'NRS-484B-283-1d1'},
    'flashing_countdown_cross': {'NRS-484B-283-1d2'},
    'flashing_no_countdown_wait': {'NRS-484B-283-1d3'},
    'walk_then_flash_continue': {'NRS-484B-283-1d1', 'NRS-484B-283-1d3'},
    'walk_then_steady_continue': {'NRS-484B-283-1d1', 'NRS-484B-283-1d4'},
}
ASSIGNMENT = 'testing__C111125__NRS-484B-307-2b__pedestrian'


def review(path: Path, case_id: str | None = None) -> dict:
    path = Path(path).resolve(strict=True)
    site = json.loads(path.read_text())
    if (site.get("diagnostic_fixture") is not False or
            site.get("reviewed_original_site") is not True or
            not site.get("review_source_id")):
        raise SourceError("reviewed original site packet required")
    verify_site(site, path.parent)
    device_ref = next(ref for ref in site["original_sources"]
                      if ref["path"] == site["device_inventory_source_path"])
    inventory = json.loads(source(device_ref, path.parent).read_text())
    applicability = inventory.get("route_applicability")
    if not isinstance(applicability, dict):
        raise SourceError("source-reviewed device route applicability missing")
    if applicability.get("route_id") != site.get("pedestrian_route_id"):
        raise SourceError("device applicability route differs")
    if applicability.get("device_id") != site["other_device_id"]:
        raise SourceError("device applicability identity differs")
    if applicability.get("applies") not in (True, False):
        raise SourceError("device applicability must be source-observed")
    law_refs = applicability.get("law_refs")
    if not isinstance(law_refs, list) or not set(law_refs) <= DEVICE_LAWS:
        raise SourceError("device applicability law references invalid")
    if applicability["applies"] and not law_refs:
        raise SourceError("applicable device lacks cited NRS 484B.283 provision")
    if not applicability.get("review_basis"):
        raise SourceError("device applicability review basis missing")
    if case_id is not None:
        if not case_id.startswith(ASSIGNMENT + '__'):
            raise SourceError('reviewed applicability wrong case identity')
        suffix = case_id.removeprefix(ASSIGNMENT + '__')
        if suffix not in CASE_PROVISIONS | {'marked_cross': set(), 'unmarked_cross': set(),
                                            'outside_cross': set()}:
            raise SourceError('reviewed applicability unknown case')
        required = CASE_PROVISIONS.get(suffix, set())
        if required and (applicability['applies'] is not True or
                         not required <= set(law_refs)):
            raise SourceError('reviewed applicability missing case provision')
    return {
        "format": "worker-pedestrian-site-preflight",
        "review_source_id": site["review_source_id"],
        "route_id": applicability["route_id"],
        "other_device_id": applicability["device_id"],
        "device_applies_to_route": applicability["applies"],
        "referenced_provisions": law_refs,
        "device_inventory_sha256": device_ref["sha256"],
        "case_id": case_id,
        "legal_verdict": None,
        "physical_acceptance": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--case")
    args = parser.parse_args()
    print(json.dumps(review(args.site, args.case), sort_keys=True))


if __name__ == "__main__":
    main()
