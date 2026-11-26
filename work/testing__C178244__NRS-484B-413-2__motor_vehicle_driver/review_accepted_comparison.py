"""Compare two independently admitted accepted signal-distance histories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from review_accepted import review
from signal_distance import EvidenceError, audit_comparison


PAIRS = {
    "business": ("business_continuous", "business_short"),
    "residential": ("residence_continuous", "residence_short"),
    "other": ("other_area_continuous", "other_area_short"),
}


def compare(repo: Path, district: str, left: dict, right: dict) -> dict:
    if district not in PAIRS:
        raise EvidenceError("unknown frozen comparison district")
    a = review(repo, left["recording_id"], left["trace"], left["video"],
               left["packet"], left["source_root"])
    b = review(repo, right["recording_id"], right["trace"], right["video"],
               right["packet"], right["source_root"])
    suffixes = tuple(row["case_id"].rsplit("__", 1)[-1] for row in (a, b))
    if suffixes != PAIRS[district]:
        raise EvidenceError("accepted cases do not form the declared district pair")
    first = json.loads(left["packet"].read_text())
    second = json.loads(right["packet"].read_text())
    physical = audit_comparison(first, second, "signal_activation_distance")
    return {
        "format": "accepted-signal-distance-comparison-review",
        "district": district,
        "accepted_recording_ids": [a["recording_id"], b["recording_id"]],
        "source_review": [a, b],
        "physical_comparison": physical,
        "finding": "source-bound physical comparison; no legal judgment or accepted-video visibility claim",
    }


def _side(args: argparse.Namespace, side: str) -> dict:
    return {name: getattr(args, side + "_" + name) for name in
            ("recording_id", "trace", "video", "packet", "source_root")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--district", choices=sorted(PAIRS), required=True)
    for side in ("left", "right"):
        parser.add_argument("--" + side + "-recording-id", required=True)
        for name in ("trace", "video", "packet", "source_root"):
            parser.add_argument("--" + side + "-" + name.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.repo.resolve(), args.district,
                             _side(args, "left"), _side(args, "right")), sort_keys=True))


if __name__ == "__main__":
    main()
