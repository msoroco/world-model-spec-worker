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


def review(path: Path) -> dict:
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
    return {
        "format": "worker-pedestrian-site-preflight",
        "review_source_id": site["review_source_id"],
        "route_id": applicability["route_id"],
        "other_device_id": applicability["device_id"],
        "device_applies_to_route": applicability["applies"],
        "referenced_provisions": law_refs,
        "device_inventory_sha256": device_ref["sha256"],
        "legal_verdict": None,
        "physical_acceptance": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(review(args.site), sort_keys=True))


if __name__ == "__main__":
    main()
