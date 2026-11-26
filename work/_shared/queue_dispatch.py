"""Run an exact queued command from its readable, assignment-sharded catalog.

The queue names the case/comparison and stage. The catalog keeps the original
command unchanged, so shortening the queue does not change the local job.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CATALOG_ROOT = ROOT / "work" / "_shared"
STAGES = {
    "prepare-delivery": "prepare_command",
    "execute-delivery": "execute_command",
    "accept-delivery": "accept_command",
    "capture_command": "capture_command",
    "native_capture_command": "native_capture_command",
    "pixel_audit_command": "pixel_audit_command",
    "qualitative_review_command": "qualitative_review_command",
    "postprocessing_command": "postprocessing_command",
    "owner_release_command": "owner_release_command",
    "additional_source_audit_command": "additional_source_audit_command",
}


def catalog_for(identifier):
    shard = int(hashlib.sha256(identifier.encode("utf-8")).hexdigest(), 16) % 16
    path = CATALOG_ROOT / f"queue-command-catalog-{shard:02x}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def resolve(identifier, stage, candidate_id=None):
    catalog = catalog_for(identifier)
    if stage == "comparison":
        if candidate_id is not None:
            raise ValueError("Comparison does not take a candidate")
        return catalog["comparisons"][identifier]
    row = catalog["cases"][identifier]
    if candidate_id is not None:
        if stage != "prepare-delivery":
            raise ValueError("Candidate is only valid for preparation")
        return row["candidate_commands"][candidate_id]
    return row[STAGES[stage]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identifier", help="Exact queued case or comparison ID")
    parser.add_argument("stage", choices=[*STAGES, "comparison"])
    parser.add_argument("candidate_id", nargs="?")
    parser.add_argument("--show", action="store_true", help="Print the exact stored command without running it")
    args = parser.parse_args()
    command = resolve(args.identifier, args.stage, args.candidate_id)
    if args.show:
        print(command)
        return 0
    return subprocess.run(["bash", "-c", command], cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
