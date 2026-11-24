"""Saved-only finalization that binds reciprocal events to a third actor."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from reciprocal_saved import SOURCE, audit_saved
from requirement_finalizer import finalize


def finalize_reciprocal(*, case_id, attempt, allow_diagnostic=False):
    saved = audit_saved(Path(attempt), case_id=case_id)
    primary = finalize(case_id=case_id, attempt=attempt,
                       allow_diagnostic=allow_diagnostic)
    if primary["original_frame_count"] != saved["joined_original_frames"]:
        raise ValueError("reciprocal and primary frame counts differ")
    observations = primary["observations"]
    observations["later_opponent_identity"] = saved["observations"]["later_opponent_actor_id"]
    observations["later_opponent_original_observations"] = saved["observations"]
    primary["source_hashes"][SOURCE] = saved["source_sha256"]
    primary["measurements"]["reciprocal_events"]["value"] = observations
    primary["measurements"]["reciprocal_events"]["sources"][SOURCE] = saved["source_sha256"]
    return primary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    args = parser.parse_args()
    result = finalize_reciprocal(case_id=args.case, attempt=args.attempt,
                                 allow_diagnostic=args.diagnostic_fixture)
    Path(args.output).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                                 encoding="utf-8")


if __name__ == "__main__":
    main()
