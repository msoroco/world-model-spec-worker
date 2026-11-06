"""Reproduce the pinned recipe restriction for partition-01 CPU diagnostics."""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
from worker_exchange.fixture_recipe import inspect, materialize

BASE = "runtime/pipeline/fixtures/retained-speed"
SOURCE = (HERE / "native/config.json").relative_to(ROOT).as_posix()
SHA = hashlib.sha256((ROOT / SOURCE).read_bytes()).hexdigest()


def recipe(target):
    return {"format": "worker-fixture-recipe-v1", "base": BASE,
            "remove": ["case.json", "config.json", "result.json"],
            "additions": [{"path": target, "source": SOURCE, "sha256": SHA}]}


with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work") as temp:
    temp = Path(temp)
    valid = temp / "valid.json"
    valid.write_text(json.dumps(recipe("extra.json")))
    inspect(ROOT, valid)
    materialize(ROOT, valid, temp / "capture")
    counts = {name: len((temp / "capture" / name).read_text().splitlines())
              for name in ("trace.jsonl", "video_frames.jsonl",
                           "capture/evidence.jsonl", "capture/native/frames.jsonl")}
    shadow = temp / "shadow.json"
    shadow.write_text(json.dumps(recipe("trace.jsonl")))
    try:
        inspect(ROOT, shadow)
    except ValueError as error:
        rejection = str(error)
    else:
        raise AssertionError("Pinned trace replacement was accepted")
    assert all(value == 3 for value in counts.values()), counts
    assert rejection == "Fixture addition shadows pinned source", rejection
    print(json.dumps({"base": BASE, "source_rows": counts,
                      "required_C10014_rows": 480,
                      "required_C10316_rows": 240,
                      "required_C104538_rows": 480,
                      "required_C382389_rows": 480,
                      "required_C394300_rows": 480,
                      "shadow_rejection": rejection}, sort_keys=True))
