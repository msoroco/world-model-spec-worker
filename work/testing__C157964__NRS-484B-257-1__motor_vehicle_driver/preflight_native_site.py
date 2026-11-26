"""CPU preflight for a reviewed original C157964 Native source packet."""

import argparse
import json
from pathlib import Path

from native_adapter import Adapter
from reviewed_site import read_reviewed_site
from yield_view import CASES, require


def preflight(packet_path, source_root, short_case_id):
    case = next((item for item in CASES if item.case_id == short_case_id), None)
    require(case is not None, "unknown exact yield case")
    site, digest = read_reviewed_site(packet_path, source_root, case)
    adapter = Adapter.__new__(Adapter)
    adapter.site = None
    adapter.case = None
    adapter.bind_site(site, case)
    return {"case_id": short_case_id, "site_packet_sha256": digest,
            "reviewed_site_source_gate_passed": True,
            "native_capture_executed": False,
            "physical_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    print(json.dumps(preflight(args.packet, args.source_root, args.case), sort_keys=True))


if __name__ == "__main__":
    main()
