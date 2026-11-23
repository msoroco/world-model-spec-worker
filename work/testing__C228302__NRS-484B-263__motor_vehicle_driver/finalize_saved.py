"""Saved-only exit measurement and independent source audit.

Input is an original-frame JSON packet retained from Native capture. This does
not run CARLA, assign a legal label, or create a canonical accepted recording.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from controlled_access_exit import CASES, measure_history
from saved_audit import audit_saved


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def process(site_path: Path, history_path: Path, packet_path: Path, output_path: Path) -> dict:
    site = json.loads(site_path.read_text())
    rows = json.loads(history_path.read_text())
    packet = json.loads(packet_path.read_text())
    case = next((case for case in CASES if case.name == packet.get("case_id")), None)
    if case is None:
        raise ValueError("unknown exact exit case")
    measured = measure_history(rows, site, case)
    if packet.get("original_history_sha256") != sha256(history_path):
        raise ValueError("sealed history hash mismatch")
    if packet.get("site_sha256") != sha256(site_path):
        raise ValueError("sealed site hash mismatch")
    expected_measurement = {**measured, "source_history_sha256": sha256(history_path)}
    if json.dumps(packet.get("measurement"), sort_keys=True) != json.dumps(expected_measurement, sort_keys=True):
        raise ValueError("packet measurement differs from original history")
    audit = audit_saved(packet)
    output = {"format": "worker-exit-saved-measurement", "case_id": case.name,
              "site_sha256": sha256(site_path), "original_history_sha256": sha256(history_path),
              "native_result_sha256": packet["native_result_sha256"],
              "measurement": measured, "independent_audit": audit,
              "legal_judgment": None, "physical_acceptance": False}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(json.dumps(output, indent=2) + "\n")
    temporary.replace(output_path)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(process(args.site, args.history, args.packet, args.output)))


if __name__ == "__main__":
    main()
