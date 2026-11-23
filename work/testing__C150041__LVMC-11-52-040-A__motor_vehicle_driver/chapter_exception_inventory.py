"""Inventory the exported Chapter 11.52 angle-parking exception source.

The frozen law export is a finite source inventory, not the complete municipal
code or a finding that a particular site has angle-parking permission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


BASE = "LVMC-11-52-040-A"
ANGLE = "LVMC-11-52-070"


def inventory(path):
    path = Path(path)
    raw = path.read_bytes()
    data = json.loads(raw)
    laws = data["laws"]
    base = laws[BASE]["law"]
    angle = laws[ANGLE]["law"]
    if ("Except as otherwise provided in this Chapter" not in base["text"] or
            "angle parking shall be permitted" not in angle["text"] or
            "front of the vehicle is pointed toward the direction of lawful traffic movement"
            not in angle["text"]):
        raise ValueError("frozen parking exception wording differs")
    return {"format": "c150041-exported-chapter-exception-inventory-v1",
            "frozen_source_path": str(path),
            "frozen_source_sha256": hashlib.sha256(raw).hexdigest(),
            "base": {"law_id": BASE, "text": base["text"],
                     "source": base["source"]},
            "potential_exception": {"law_id": ANGLE, "text": angle["text"],
                                    "source": angle["source"],
                                    "site_conditions_to_acquire": [
                                        "City Traffic Engineer permission for the exact street",
                                        "signage or markings indicating where angle parking is permitted",
                                        "original vehicle front direction during standing or parking"]},
            "review_scope": "exported law inventory only; not complete Chapter review",
            "site_exception_status": "unresolved",
            "legal_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = inventory(args.source)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"potential_exception": result["potential_exception"]["law_id"],
                      "site_exception_status": result["site_exception_status"]}))


if __name__ == "__main__":
    main()
