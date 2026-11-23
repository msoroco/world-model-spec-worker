"""Entry for exact parked-lamp construction bundles.

Offline mode verifies the authored case and source contract. Native mode needs
an operator supplied site packet; no source geography is synthesized here.
"""

import argparse
import json
import os
from pathlib import Path

from parked_lamps import CASES, LAW, validate_site

ROOT = Path(__file__).resolve().parent


def check():
    config = json.loads((ROOT / "config.json").read_text())
    key = config["case_key"]
    if key not in CASES or config["law_id"] != LAW or config["cell_id"] != "C229398":
        raise ValueError("frozen case identity mismatch")
    if config["selected_case_id"] != config["assignment_id"] + "__" + key:
        raise ValueError("exact selected case mismatch")
    if config["rate_hz"] != 20 or config["duration_s"] != 45:
        raise ValueError("capture cadence mismatch")
    if [c["name"] for c in config["cameras"]] != ["front", "rear", "left", "right"]:
        raise ValueError("four-camera plan mismatch")
    if config["case"] != CASES[key]:
        raise ValueError("case conditions mismatch")
    return config


def native(output_dir, host, port):
    config = check()
    source = os.environ.get("PARKED_LAMP_SITE_PACKET")
    if not source:
        raise ValueError("PARKED_LAMP_SITE_PACKET source path is required for Native capture")
    packet = json.loads(Path(source).read_text())
    validate_site(packet, config["case_key"], packet["map_sha256"])
    raise NotImplementedError("four synchronized original cameras and sealed Native capture are not yet implemented")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps({"exact_case_checked": check()["selected_case_id"], "simulation_started": False}))
        return
    if not args.output_dir:
        parser.error("--output-dir required for Native capture")
    native(args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
