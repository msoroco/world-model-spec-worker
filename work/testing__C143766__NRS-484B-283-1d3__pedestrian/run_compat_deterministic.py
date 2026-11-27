"""Run frozen compatibility with a stable .runtime-work fixture path.

The missing-source traceback includes its temporary path. A stable path makes
the receipt reproducible while the selected manifest binds that receipt.
"""

import argparse
import contextlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    for name in ("manifest", "case", "candidate", "output", "library", "validator"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    output = Path(args.output).resolve()
    scratch = repo / ".runtime-work" / "c143766-1d3-owner-nov26/fixture-stable" / (
        args.case.split("__")[-1] + "-" + args.candidate)
    output_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "/nonexistent")).resolve()
    if repo / ".runtime-work" not in output_root.parents:
        raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    sys.path[:0] = [str(repo / "runtime"), str(repo / "runtime/scenario_pipeline")]
    from scenario_pipeline.worker_exchange import package_compatibility

    original = tempfile.TemporaryDirectory

    @contextlib.contextmanager
    def stable_temporary_directory(*positional, **keyword):
        if (keyword.get("prefix") == "fixture-" and
                Path(keyword.get("dir", "")).resolve() == output.parent):
            scratch.parent.mkdir(parents=True, exist_ok=True)
            if scratch.exists():
                shutil.rmtree(scratch)
            scratch.mkdir()
            try:
                yield str(scratch)
            finally:
                shutil.rmtree(scratch)
        else:
            with original(*positional, **keyword) as temporary:
                yield temporary

    package_compatibility.tempfile.TemporaryDirectory = stable_temporary_directory
    receipt = package_compatibility.run(args.manifest, args.case, args.output,
        args.library, args.validator, args.candidate)
    print(json.dumps({"case_id": receipt["case_id"],
                      "candidate_id": receipt["candidate_id"],
                      "passed": receipt["passed"]}))


if __name__ == "__main__":
    main()
