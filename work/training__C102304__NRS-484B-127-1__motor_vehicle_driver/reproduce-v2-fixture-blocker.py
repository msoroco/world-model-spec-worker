"""Reproduce the pinned strict v2 recipe conflict for this 900-frame case."""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
from worker_exchange.fixture_recipe import inspect, materialize

HERE = Path(__file__).resolve().parent
BASE = "runtime/pipeline/fixtures/retained-speed"
SOURCE = (HERE / "native/config.json").relative_to(ROOT).as_posix()
HASH = hashlib.sha256((ROOT / SOURCE).read_bytes()).hexdigest()


def recipe(target):
    return {"format": "worker-fixture-recipe-v1", "base": BASE,
            "remove": ["case.json", "config.json", "result.json"],
            "additions": [{"path": target, "source": SOURCE, "sha256": HASH}]}


def main():
    with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work") as temp:
        folder = Path(temp)
        valid = folder / "valid.json"
        valid.write_text(json.dumps(recipe("extra.json")))
        inspect(ROOT, valid)
        materialize(ROOT, valid, folder / "materialized")
        capture = folder / "materialized"
        rows = {name: len((capture / name).read_text().splitlines())
                for name in ("trace.jsonl", "video_frames.jsonl",
                             "capture/evidence.jsonl", "capture/native/frames.jsonl")}
        blocked = folder / "shadow.json"
        blocked.write_text(json.dumps(recipe("trace.jsonl")))
        try:
            inspect(ROOT, blocked)
        except ValueError as error:
            rejection = str(error)
        else:
            raise AssertionError("Existing trace was allowed to be replaced")
        assert all(count == 3 for count in rows.values()), rows
        assert rejection == "Fixture addition shadows pinned source", rejection
        print(json.dumps({"base": BASE, "source_rows": rows,
                          "required_case_rows": 900, "shadow_rejection": rejection,
                          "recipe_source": "fixture_recipe.inspect/materialize"}, sort_keys=True))


if __name__ == "__main__":
    main()
