"""Pinned four-view composition and decode on original-sized synthetic sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
from worker_exchange.media import compose_four_views, audit


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    package = json.loads((HERE / "exact-package-summary.json").read_text())
    row = next(item for item in package["results"] if item["case_id"].endswith("below_80_mph")
               and item["candidate_id"] == "primary")
    output = Path(row["positive_output"])
    sources = {"overview": output / "overview.mkv",
               "approach": output / "ego_forward.mkv",
               "reference_corner": output / "junction.mkv",
               "driver_reference": output / "ego_side.mkv"}
    before = {name: sha(path) for name, path in sources.items()}
    scratch = Path(tempfile.mkdtemp(dir=ROOT / ".runtime-work",
                                        prefix="c111294-compose-probe-"))
    composed = compose_four_views(sources, output / "video_frames.jsonl", scratch / "raw.mkv")
    decoded = audit(scratch / "raw.mkv", 480,
                    mapping_sha256=sha(output / "video_frames.jsonl"),
                    receipt=scratch / "raw-decode.json")
    if {name: sha(path) for name, path in sources.items()} != before:
        raise ValueError("Composition changed original camera source")
    if not decoded["passed"] or decoded["frames"] != 480:
        raise ValueError("Composed source decode incomplete")
    result = {"format": "c111294-synthetic-four-view-composition-v1",
              "source_hashes": before, "composition": composed,
              "decode": decoded, "original_sources_preserved": True,
              "synthetic_diagnostic": True, "accepted": False, "ready": False}
    (HERE / "synthetic-composition.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True, "frames": 480,
                      "dimensions": decoded["dimensions"],
                      "synthetic_diagnostic": True}, sort_keys=True))


if __name__ == "__main__": main()
