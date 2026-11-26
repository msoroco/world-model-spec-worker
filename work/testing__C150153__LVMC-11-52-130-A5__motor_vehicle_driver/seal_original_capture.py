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
           "trace.jsonl", "video_frames.jsonl",
           "reviewed-site/packet.json",
           *(name + ".mkv" for name in CAMERAS))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal(attempt: Path, site_packet: Path, source_root: Path,
         owner_receipt: Path, owner_receipt_sha256: str) -> dict:
    attempt = Path(attempt).resolve()
    site_packet = Path(site_packet).resolve()
    owner_receipt = Path(owner_receipt).resolve()
    output = attempt / "delivery-seal.json"
    if output.exists():
        raise ValueError("refusing to overwrite original capture seal")
    if owner_receipt.is_relative_to(attempt):
        raise ValueError("owner release receipt must be external to capture")
    if _sha(owner_receipt) != owner_receipt_sha256:
        raise ValueError("owner release receipt hash differs")
    reviewed = verify(site_packet, source_root)
    acquisition = json.loads((attempt / 'capture-seal.json').read_text())
    native_exit = json.loads((attempt / 'native-exit.json').read_text())
    owner_receipt_raw = owner_receipt.read_text()
    receipt = json.loads(owner_receipt_raw)
    case_id = acquisition.get('case_id', '')
    prefix = reviewed["assignment_id"] + "__"
    if not case_id.startswith(prefix) or case_id[len(prefix):] not in {c.id for c in CASES}:
        raise ValueError("owner release exact case differs")
    if (acquisition.get('format') != 'sidewalk-elevator-native-acquisition-seal' or
            acquisition.get('site_packet_sha256') != _sha(site_packet) or
            acquisition.get('provenance_kind') != 'native' or
            acquisition.get('events') != ['capture_finished', 'encoders_closed', 'restoration_verified'] or
            acquisition.get('frames') != 900 or acquisition.get('capture_rate_hz') != 20 or
            acquisition.get('native_revision', {}).get('construction_sha256') != _sha(attempt / 'construction.json') or
            acquisition.get('native_revision', {}).get('runner_sha256') != _sha(attempt / 'runner.py') or
            native_exit.get('event') != 'native_exit' or
            native_exit.get('capture_seal_sha256') != _sha(attempt / 'capture-seal.json') or
            native_exit.get('native_revision') != acquisition['native_revision'] or
            native_exit.get('capture_command_failed') is True or
            native_exit.get('native_process_exit_code', 0) != 0 or
            receipt.get('event') != 'owner_released' or
            receipt.get('operator_attested') is not True or
            receipt.get('native_construction_sha256') != _sha(attempt / 'construction.json') or
            receipt.get('native_exit_sha256') != _sha(attempt / 'native-exit.json')):
        raise ValueError("original Native owner release incomplete")
    sealed_sources = acquisition.get('sources')
    if not isinstance(sealed_sources, dict) or not set(SOURCES) <= set(sealed_sources):
        raise ValueError('original Native source inventory incomplete')
    hashes = {}
    for name in sealed_sources:
        relative = Path(name)
        path = (attempt / relative).resolve()
        if relative.is_absolute() or '..' in relative.parts or not path.is_relative_to(attempt):
            raise ValueError('original Native source path escapes attempt')
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError("original Native source missing: " + name)
        hashes[name] = _sha(path)
    if sealed_sources != hashes:
        raise ValueError("owner release original source hashes differ")
    copied_packet = attempt / 'reviewed-site/packet.json'
    if _sha(copied_packet) != _sha(site_packet):
        raise ValueError('copied reviewed site packet differs')
    verify(copied_packet, attempt / 'reviewed-site/sources')
    seal_record = {"format": "sidewalk-elevator-native-seal", "case_id": case_id,
                   "site_packet_sha256": _sha(site_packet), "frames": 900,
                   "capture_rate_hz": 20, "owner_released": True,
                   "restoration_verified": True, "native_process_exit_code": 0,
                   "encoder_exit_codes": {name: 0 for name in CAMERAS},
                   "provenance_kind": "original_native", "sources": hashes,
                   "owner_receipt_sha256": owner_receipt_sha256,
                   "owner_receipt_raw": owner_receipt_raw}
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
