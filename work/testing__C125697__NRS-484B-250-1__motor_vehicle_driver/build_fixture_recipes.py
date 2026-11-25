"""Pin case-specific CPU fixture specifications for runtime materialization."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    marker = ROOT / "diagnostic-policy.txt"
    marker.write_text("CPU software diagnostic only; no physical or legal acceptance.\n")
    for suffix in ("precedence", "advance"):
        spec = ROOT / ("diagnostic-" + suffix + ".json")
        source = spec.relative_to(REPO).as_posix()
        policy = marker.relative_to(REPO).as_posix()
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "diagnostic-policy.txt", "source": policy,
                               "sha256": sha(marker)}],
                  "generator": {"source": source, "sha256": sha(spec)}}
        (ROOT / ("fixture-recipe-" + suffix + ".json")).write_text(
            json.dumps(recipe, indent=2) + "\n")


if __name__ == "__main__":
    build()
