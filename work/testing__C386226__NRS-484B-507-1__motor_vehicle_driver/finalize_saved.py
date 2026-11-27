"""Recorded-only freight finalizer; never simulates conduct or infers a verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from freight_zone import CASES, measure_history, validate_site
from saved_audit import audit_original_history


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize(history_path: Path, site_path: Path, seal_path: Path, output_path: Path) -> dict:
    seal = json.loads(seal_path.read_text())
    site = json.loads(site_path.read_text())
    case = next((item for item in CASES if item.name == seal.get("case_id")), None)
    if case is None:
        raise ValueError("unknown sealed freight case")
    if sha(site_path) != seal.get("site_sha256"):
        raise ValueError("freight site hash mismatch")
    validate_site(site, case)
    audit = audit_original_history(history_path, seal.get("original_history_sha256"),
                                   case.name, site["zone"]["boundary_source_sha256"],
                                   site["regulations"]["source_sha256"])
    rows = [json.loads(line) for line in history_path.read_text().splitlines() if line]
    measurement = measure_history(rows, case, site)
    result = {"case_id": case.name, "site_sha256": seal["site_sha256"],
              "original_history_sha256": audit["original_history_sha256"],
              "first_original_frame": audit["first_original_frame"],
              "last_original_frame": audit["last_original_frame"],
              "measurement": measurement, "delivery_audit": audit,
              "physical_visibility_verified": False, "legal_judgment": None}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp.write_text(json.dumps(result, indent=2) + "\n")
    tmp.replace(output_path)
    return result


def main():
    parser = argparse.ArgumentParser()
    for arg in ("history", "site", "seal", "output"):
        parser.add_argument("--" + arg, type=Path, required=True)
    args = parser.parse_args()
    finalize(args.history, args.site, args.seal, args.output)


if __name__ == "__main__":
    main()
