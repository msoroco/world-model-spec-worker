"""CPU proof of the saved fixture source gate; never original physical evidence."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

from geometry import FIXTURE_BOUNDS, SIDEWALK_BOUNDS, open_drive
from source_review import ROLES, reviewed_context


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def build(path):
    path.mkdir()
    (path / "road.xodr").write_text(open_drive())
    put(path / "fixture-inventory.json", {"fixture_bounds_m": FIXTURE_BOUNDS,
        "sidewalk_bounds_m": SIDEWALK_BOUNDS,
        "fixture_proxy_blueprint_id": "static.prop.box"})
    put(path / "acquisition-provenance.json", {"provenance_kind": "synthetic_fixture"})
    for role in ROLES:
        source = path / "source-review" / (role + ".source.txt")
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("Synthetic CPU source for " + role + " only\n")
        record = {"role": role, "source_sha256": sha(source),
                  "road_sha256": sha(path / "road.xodr"),
                  "provenance_kind": "synthetic_fixture", "reviewed": True}
        if role == "fixture-identity":
            record["fixture_kind"] = "sidewalk_elevator"
        elif role == "fixture-geometry":
            record["fixture_bounds_m"] = FIXTURE_BOUNDS
        elif role == "sidewalk-geometry":
            record["sidewalk_bounds_m"] = SIDEWALK_BOUNDS
        else:
            record["front_is_road_facing"] = True
        put(path / "source-review" / (role + ".json"), record)


def reject(path, expected):
    try:
        reviewed_context(path)
    except ValueError as error:
        if expected in str(error):
            return str(error)
        raise
    raise AssertionError("Source review accepted defective source: " + expected)


def main(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    good = root / "good"
    build(good)
    context = reviewed_context(good)
    if not context["diagnostic_fixture"]:
        raise AssertionError("Diagnostic provenance lost")
    tests = {}
    for label, mutation, expected in (
        ("missing_identity", lambda p: (p / "source-review/fixture-identity.json").unlink(),
         "Missing required source"),
        ("tampered_geometry", lambda p: (p / "source-review/fixture-geometry.source.txt").write_text("tampered\n"),
         "Source role hash mismatch"),
        ("unsupported_kind", lambda p: update(p / "source-review/fixture-identity.json", "fixture_kind", "box"),
         "identity not sourced"),
        ("unknown_front", lambda p: update(p / "source-review/front-orientation.json", "front_is_road_facing", False),
         "orientation not sourced"),
        ("proxy_original", lambda p: (p / "acquisition-provenance.json").unlink(),
         "Generic fixture proxy")):
        bad = root / label
        shutil.copytree(good, bad)
        mutation(bad)
        tests[label] = reject(bad, expected)
    return {"passed": True, "diagnostic_only": True, "original_fixture_observed": False,
            "positive": {"fixture_kind": context["fixture_kind"],
                         "source_hashes": {k: v for k, v in context.items() if k.endswith("sha256")}},
            "negative": tests}


def update(path, key, value):
    record = json.loads(path.read_text())
    record[key] = value
    put(path, record)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: prove_source_review.py SCRATCH")
    print(json.dumps(main(sys.argv[1]), indent=2))
