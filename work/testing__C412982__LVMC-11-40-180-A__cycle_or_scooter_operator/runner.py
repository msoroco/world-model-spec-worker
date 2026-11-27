"""Exact, source gated LVMC 11.40.180(A) Native capture entrypoint."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from fremont_180 import AID, BY_SUFFIX, original_site

ROOT = Path(__file__).resolve().parent


def checked_config():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    suffix = cfg.get("selected_case_id", "").removeprefix(AID + "__")
    if (cfg.get("assignment_id") != AID or suffix not in BY_SUFFIX or
            cfg.get("law_id") != "LVMC-11-40-180-A" or
            cfg.get("cell_id") != "C412982" or
            cfg.get("actor") != "cycle_or_scooter_operator" or
            cfg.get("rate_hz") != 20 or cfg.get("duration_s") != 45):
        raise ValueError("frozen Fremont case or capture contract differs")
    return cfg, BY_SUFFIX[suffix]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args(argv)
    config, case = checked_config()
    if args.check:
        print(json.dumps({"case_id": config["selected_case_id"],
                          "capture_contract_checked": True,
                          "reviewed_original_fremont_site_required": True}))
        return 0
    if not args.output_dir:
        parser.error("--output-dir required")
    packet = os.environ.get("C412982_LVMC180_REVIEWED_SITE_PACKET")
    if not packet:
        raise ValueError("C412982_LVMC180_REVIEWED_SITE_PACKET original packet required")
    packet_path = Path(packet).resolve()
    site = original_site(packet_path, case)
    from native_fremont import run_native
    run_native(config, case, site, packet_path, Path(args.output_dir), args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
