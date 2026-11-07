"""Reproduce pinned v2 fixture-recipe incompatibility with 480-frame cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
from worker_exchange.fixture_recipe import inspect


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    base = ROOT / "runtime/pipeline/fixtures/retained-speed"
    base_trace = base / "trace.jsonl"
    count = len(base_trace.read_text().splitlines())
    assert count == 3
    addition = HERE / "draft-fixtures/below_80_mph-synthetic-native-samples.jsonl"
    scratch = Path(tempfile.mkdtemp(dir=ROOT / ".runtime-work",
                                        prefix="c111294-v2-recipe-limit-"))
    recipe = {"format": "worker-fixture-recipe-v1",
        "base": str(base.relative_to(ROOT)),
        "remove": ["case.json", "config.json", "result.json"],
        "additions": [{"path": "trace.jsonl",
                       "source": str(addition.relative_to(ROOT)),
                       "sha256": sha(addition)}]}
    path = scratch / "shadow.json"
    path.write_text(json.dumps(recipe) + "\n")
    try:
        inspect(ROOT, path)
    except ValueError as error:
        shadow_error = str(error)
        if "shadows pinned source" not in shadow_error:
            raise
    else:
        raise ValueError("Pinned fixture unexpectedly allows replacing trace")
    recipe["remove"].append("trace.jsonl")
    recipe["additions"][0]["path"] = "native_samples.jsonl"
    second = scratch / "remove.json"
    second.write_text(json.dumps(recipe) + "\n")
    try:
        inspect(ROOT, second)
    except ValueError as error:
        remove_error = str(error)
        if "must remove only" not in remove_error:
            raise
    else:
        raise ValueError("Pinned fixture unexpectedly allows removing trace")
    report = {"format": "c111294-v2-recipe-capability-reproducer-v1",
        "base": str(base.relative_to(ROOT)), "base_trace_sha256": sha(base_trace),
        "base_trace_frames": count, "case_required_frames": 480,
        "replacement_error": shadow_error, "removal_error": remove_error,
        "strict_v2_receipt_produced": False,
        "scope": "pinned recipe limitation; worker-owned delivery construction remains unfinished"}
    (HERE / "v2-recipe-limit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__": main()
