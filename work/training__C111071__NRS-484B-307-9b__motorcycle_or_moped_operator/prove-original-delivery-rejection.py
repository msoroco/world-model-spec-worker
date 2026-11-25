"""Exercise the independent audit's original-source gate on public fixtures."""

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import delivery_audit


ROOT = Path(__file__).resolve().parent
CASE = "training__C111071__NRS-484B-307-9b__motorcycle_or_moped_operator__probe_1"


def require_error(call, expected):
    try:
        call()
    except ValueError as exc:
        if expected not in str(exc):
            raise AssertionError(f"Expected {expected!r}, got {exc!r}") from exc
    else:
        raise AssertionError(f"Expected rejection: {expected}")


def main():
    saved = json.loads((ROOT / "selected-native/probe_1/saved-proof.json").read_text())
    version = Path(saved["processing_receipt"]["version"])
    processing = version / "processing.json"
    attempt = version.parents[1] / "attempt"
    run = lambda: delivery_audit.audit(CASE, "primary", attempt, processing)
    require_error(run, "Original Native source required")

    original_read = delivery_audit.read
    manifest_hash = hashlib.sha256((ROOT / "execution-manifest.json").read_bytes()).hexdigest()

    def advertised_original(path):
        value = original_read(path)
        if path == attempt / "capture/manifest.json":
            return {**value, "source_kind": "original_native"}
        if path == attempt / "candidate-selection.json":
            return {**value, "manifest_sha256": manifest_hash}
        return value

    with patch.object(delivery_audit, "read", side_effect=advertised_original):
        require_error(run, "Missing original source: native_raw_readback.jsonl")
    print(json.dumps({
        "format": "c111071-original-delivery-rejection-v1",
        "case_id": CASE,
        "diagnostic_fixture_only": True,
        "tested_rejections": [
            "Original Native source required",
            "Missing original source: native_raw_readback.jsonl",
        ],
        "original_native_observed": False,
    }, indent=2))


if __name__ == "__main__":
    main()
