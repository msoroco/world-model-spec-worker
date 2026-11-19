"""Verify exact original saved-only receipts without a manifest-hash cycle."""

import base64
import hashlib
import json
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUFFIXES = ("entry_before_red", "entry_at_red", "entry_after_red", "stops_on_yellow")
CANDIDATES = ("primary", "fallback1", "fallback2", "fallback3")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    archive = json.loads((HERE / "saved-processing-receipts.json").read_text())
    if archive.get("encoding") != "zlib+base64":
        raise ValueError("Wrong original receipt archive encoding")
    raw = zlib.decompress(base64.b64decode(archive["payload"]))
    if sha(raw) != archive["uncompressed_sha256"] or len(raw) != archive["uncompressed_bytes"]:
        raise ValueError("Original receipt archive changed")
    rows = json.loads(raw)["receipts"]
    if len(rows) != 16:
        raise ValueError("Missing selected saved-only receipt")
    found = set()
    for row in rows:
        receipt = row["receipt"]
        original = (json.dumps(receipt, indent=2, ensure_ascii=True) + "\n").encode()
        if sha(original) != row["original_sha256"]:
            raise ValueError("Original saved-only receipt bytes changed")
        case = receipt.get("case_id", "")
        suffix = case.removeprefix(HERE.name + "__")
        candidate = receipt.get("candidate_id")
        if (case != HERE.name + "__" + suffix or suffix not in SUFFIXES or
                candidate not in CANDIDATES or (suffix, candidate) in found):
            raise ValueError("Saved-only exact case/candidate differs")
        if (receipt.get("passed") is not True or receipt.get("recorded_only") is not True or
                receipt.get("originals_preserved") is not True or
                receipt.get("physical_acceptance_claimed") is not False or
                receipt.get("legal_acceptance_claimed") is not False or
                receipt.get("timestamp_joins", {}).get("frames") != 900 or
                receipt.get("timestamp_joins", {}).get("passed") is not True):
            raise ValueError("Saved-only source processing did not pass")
        found.add((suffix, candidate))
    if found != {(suffix, candidate) for suffix in SUFFIXES for candidate in CANDIDATES}:
        raise ValueError("Saved-only candidate coverage incomplete")
    for suffix in SUFFIXES:
        print(suffix + ": primary,fallback1,fallback2,fallback3 passed; "
              "recorded_only=true; originals_preserved=true; frames=900; "
              "physical_acceptance_claimed=false")


if __name__ == "__main__":
    main()
