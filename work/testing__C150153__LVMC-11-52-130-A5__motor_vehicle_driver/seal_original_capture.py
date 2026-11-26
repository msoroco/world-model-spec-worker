"""Seal four original cameras only after independent owner-release evidence.

The source files must already have been acquired by a Native camera adapter.
This command never creates or substitutes camera frames.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from independent_delivery_audit import CAMERAS, audit
from parking import CASES
from reviewed_site import verify


SOURCES = ("history.jsonl", "camera-frame-map.jsonl", "comparison-context.json",
           *(name + ".mkv" for name in CAMERAS))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal(attempt: Path, site_packet: Path, source_root: Path,
         owner_receipt: Path, owner_receipt_sha256: str) -> dict:
    attempt = Path(attempt).resolve()
    site_packet = Path(site_packet).resolve()
    owner_receipt = Path(owner_receipt).resolve()
    output = attempt / "capture-seal.json"
    if output.exists():
        raise ValueError("refusing to overwrite original capture seal")
    if owner_receipt.is_relative_to(attempt):
        raise ValueError("owner release receipt must be external to capture")
    if _sha(owner_receipt) != owner_receipt_sha256:
        raise ValueError("owner release receipt hash differs")
    reviewed = verify(site_packet, source_root)
    receipt = json.loads(owner_receipt.read_text())
    case_id = receipt.get("case_id", "")
    prefix = reviewed["assignment_id"] + "__"
    if not case_id.startswith(prefix) or case_id[len(prefix):] not in {c.id for c in CASES}:
        raise ValueError("owner release exact case differs")
    if (receipt.get("format") != "sidewalk-elevator-native-owner-release" or
            receipt.get("site_packet_sha256") != _sha(site_packet) or
            receipt.get("provenance_kind") != "original_native" or
            receipt.get("owner_released") is not True or
            receipt.get("restoration_verified") is not True or
            receipt.get("native_process_exit_code") != 0 or
            any(receipt.get("encoder_exit_codes", {}).get(name) != 0 for name in CAMERAS)):
        raise ValueError("original Native owner release incomplete")
    hashes = {}
    for name in SOURCES:
        path = attempt / name
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError("original Native source missing: " + name)
        hashes[name] = _sha(path)
    if receipt.get("source_hashes") != hashes:
        raise ValueError("owner release original source hashes differ")
    seal_record = {"format": "sidewalk-elevator-native-seal", "case_id": case_id,
                   "site_packet_sha256": _sha(site_packet), "frames": 900,
                   "capture_rate_hz": 20, "owner_released": True,
                   "restoration_verified": True, "native_process_exit_code": 0,
                   "encoder_exit_codes": receipt["encoder_exit_codes"],
                   "provenance_kind": "original_native", "sources": hashes,
                   "owner_receipt_sha256": owner_receipt_sha256}
    output.write_text(json.dumps(seal_record, indent=2, sort_keys=True) + "\n")
    try:
        proof = audit(attempt, site_packet, source_root)
    except Exception:
        output.unlink()
        raise
    return proof


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--site-packet", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--owner-receipt", type=Path, required=True)
    parser.add_argument("--owner-receipt-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("original delivery receipt already exists")
    proof = seal(args.attempt, args.site_packet, args.source_root,
                 args.owner_receipt, args.owner_receipt_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
