"""Source-gated exact NRS 484B.117(1) sidewalk Native entrypoint."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from sidewalk_case import BY_SUFFIX, validate_case_site
from site_review import reviewed_site

ROOT = Path(__file__).resolve().parent
AID = "testing__C412982__NRS-484B-117-1__motor_vehicle_driver"


def config():
    value = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    suffix = value.get("selected_case_id", "").removeprefix(AID + "__")
    if (value.get("assignment_id") != AID or suffix not in BY_SUFFIX or
            value.get("law_id") != "NRS-484B-117-1" or
            value.get("cell_id") != "C412982" or
            value.get("actor") != "motor_vehicle_driver" or
            value.get("rate_hz") != 20 or value.get("duration_s") != 45):
        raise ValueError("frozen sidewalk case or capture contract differs")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args(argv)
    cfg = config()
    if args.check:
        print(json.dumps({"case_id": cfg["selected_case_id"],
                          "capture_contract_checked": True,
                          "reviewed_original_site_required": True}))
        return 0
    if not args.output_dir:
        parser.error("--output-dir required")
    packet = os.environ.get("C412982_REVIEWED_SITE_PACKET")
    if not packet:
        raise ValueError("C412982_REVIEWED_SITE_PACKET original reviewed packet required")
    path = Path(packet).resolve()
    site = reviewed_site(path, cfg["selected_case_id"])
    validate_case_site(BY_SUFFIX[cfg["selected_case_id"].removeprefix(AID + "__")], site)
    from native_sidewalk import run_native
    run_native(cfg, site, path, Path(args.output_dir), args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
