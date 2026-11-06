"""Reproduce the pinned three-frame/480-frame strict recipe limitation."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
from worker_exchange.fixture_recipe import inspect


def main():
    base = ROOT / "runtime/pipeline/fixtures/retained-speed"
    source = HERE / "fixtures/condition_a/native_samples.jsonl"
    recipe = ROOT / ".runtime-work/c110741-113-2-v2-shadow-repro.json"
    recipe.write_text(json.dumps({
        "format": "worker-fixture-recipe-v1",
        "base": str(base.relative_to(ROOT)),
        "remove": ["case.json", "config.json", "result.json"],
        "additions": [{"path": "trace.jsonl",
                       "source": str(source.relative_to(ROOT)),
                       "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}]}, indent=2))
    try:
        inspect(ROOT, recipe)
    except ValueError as error:
        if str(error) != "Fixture addition shadows pinned source":
            raise
    else:
        raise AssertionError("Unexpectedly allowed replacement of frozen 3-frame trace")
    rows = {name: len((base / name).read_text().splitlines()) for name in
            ("trace.jsonl", "capture/evidence.jsonl", "video_frames.jsonl")}
    if set(rows.values()) != {3}:
        raise AssertionError("Pinned base row count changed")
    report = {"reproduced": True, "error": "Fixture addition shadows pinned source",
              "source_file": "runtime/pipeline/scenario_pipeline/worker_exchange/fixture_recipe.py",
              "runtime_base": str(base.relative_to(ROOT)), "base_rows": rows,
              "exact_bundle_required_frames": 480,
              "scope": "strict v2 recipe contract limitation; not an original physical observation"}
    (HERE / "v2-recipe-diagnostic.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__": main()
