"""Check the compact synthetic frame map through pinned recipe materialization."""
import hashlib
import json
import tempfile
from pathlib import Path

from worker_exchange.fixture_recipe import inspect, materialize


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE / "current-tour-bus-below-compact-video_frames.jsonl"
RECIPE = HERE / "current-tour-bus-below-compact-map-recipe.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    inspect(ROOT, RECIPE)
    scratch = ROOT / ".runtime-work/owner150142"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch, prefix="compact-map-recipe-") as name:
        output = Path(name) / "fixture"
        proof = materialize(ROOT, RECIPE, output)
        rows = [json.loads(line) for line in (output / "video_frames.jsonl").open()]
        assert len(rows) == 36120
        assert all(row["video_frame"] == i and row["carla_frame"] == i
                   for i, row in enumerate(rows))
        result = {"format": "c150142-compact-long-map-recipe-proof-v1",
                  "source_sha256": sha(SOURCE), "source_bytes": SOURCE.stat().st_size,
                  "frames": len(rows), "recipe_sha256": proof["recipe_sha256"],
                  "fixture_sha256": proof["fixture_sha256"],
                  "official_long_compatibility_passed": False}
        assert result["source_bytes"] <= 2 * 1024 * 1024
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
