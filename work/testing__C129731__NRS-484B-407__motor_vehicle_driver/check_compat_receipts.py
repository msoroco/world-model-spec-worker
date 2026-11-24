"""Revalidate the four pinned diagnostic compatibility receipts."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> None:
    assignment = Path(__file__).resolve().parent
    repository = assignment.parents[1]
    scratch = repository / ".runtime-work"
    output = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    temporary = Path(os.environ.get("TMPDIR", "")).resolve()
    if not output.is_relative_to(scratch) or not temporary.is_relative_to(scratch):
        raise ValueError("Runtime output and temporary roots must be under .runtime-work")
    sys.path.insert(0, str(repository / "runtime" / "scenario_pipeline"))
    from worker_exchange.common import read
    from worker_exchange.package_compatibility import check_receipts

    manifest = read(assignment / "execution-manifest.draft.json")
    check_receipts(repository, assignment, manifest)
    print(json.dumps({"format": "c129731-compatibility-receipt-check-v1",
                      "passed": True,
                      "case_ids": [case["case_id"] for case in manifest["cases"]]}))


if __name__ == "__main__":
    main()
