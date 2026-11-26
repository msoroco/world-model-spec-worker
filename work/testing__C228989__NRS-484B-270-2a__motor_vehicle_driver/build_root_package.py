"""Materialize a reviewable canonical root package from one selected case."""

import json
from pathlib import Path

from package_spec import AID, CHANNELS


HERE = Path(__file__).resolve().parent


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("root package exceeds return limit")


def build():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    if manifest.get("assignment_id") != AID or len(manifest["cases"]) != 14:
        raise ValueError("complete exact selected manifest required")
    source = json.loads((HERE / manifest["cases"][0]["construction"]).read_text())
    if source["case_id"] != manifest["cases"][0]["case_id"]:
        raise ValueError("selected root construction mismatch")
    source["files"] = [item for item in source["files"]
                       if item["path"] != "tests/test_bundle.py"]
    old_bundle_test = HERE / "tests/test_bundle.py"
    if old_bundle_test.is_file():
        old_bundle_test.unlink()
    for item in source["files"]:
        path = HERE / item["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item["content"])
    source["measurement_plan"] = {"rate_hz": 20, "duration_s": 45,
                                  "required_channels": [name for name, _, _ in CHANNELS]}
    source["static_checks"] = ["exact source and case identity",
                                "source-hashed Native map, lanes and rider type",
                                "900 original frame and four camera join"]
    source["termination_rules"] = ["900 consecutive original 20 Hz Native frames",
                                    "brake, destroy owned actors and restore world on every exit"]
    source["mechanisms"] = ["reviewed Native lane and actor construction",
                            "per-frame physical controller and four camera acquisition",
                            "saved source measurement and independent delivery audit"]
    write(HERE / "construction.json", source)
    return source["case_id"]


if __name__ == "__main__":
    print("root exact case:", build())
