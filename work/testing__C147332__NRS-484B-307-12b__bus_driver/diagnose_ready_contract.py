"""Exercise ready-only static contracts in memory; never change result.json.

This is a schema diagnostic. It does not establish delivery readiness or source
review. The exact worker_check strict command remains the acceptance gate.
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    scratch = (repo / ".runtime-work").resolve()
    output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
    if not output or not Path(output).resolve().is_relative_to(scratch):
        raise ValueError("set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
    sys.path.insert(0, str(repo / "runtime" / "scenario_pipeline"))
    from worker_exchange import preparation

    folder = Path(__file__).resolve().parent
    aid = folder.name
    result_path = folder / "result.json"
    queue = json.loads((folder / "queue-entries.partial.json").read_text())
    original_read = preparation.read

    def diagnostic_read(target):
        value = original_read(target)
        if Path(target).resolve() == result_path.resolve():
            value = copy.deepcopy(value)
            if value["status"] != "partial":
                raise ValueError("diagnostic expects truthful partial result on disk")
            value["status"] = "ready"
            value["readiness_kind"] = "delivery_prepared"
            value["first_gpu_delivery_command"] = queue["cases"][0]["execute_command"]
        return value

    preparation.read = diagnostic_read
    try:
        preparation.check(repo, complete=True, require_ready=True, assignment=aid)
    finally:
        preparation.read = original_read
    if original_read(result_path)["status"] != "partial":
        raise ValueError("on-disk result changed during diagnostic")
    print("in-memory ready static contracts pass; on-disk result remains partial")


if __name__ == "__main__":
    main()
