"""Exercise independent audit with synthetic sources and sealed-source negative."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from delivery_audit import audit, CAMERAS, SOURCES, _independent_review

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--negative", action="store_true")
    parser.add_argument("--negative-incomplete-seal", action="store_true")
    args = parser.parse_args()
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    entry = next(item for item in manifest["cases"] if item["case_id"] == args.case)
    suffix = args.case.removeprefix(HERE.name + "__")
    compatible = REPO / ".runtime-work/c202480-owner" / (
        "compat-inside-15-v5" if suffix == "inside_15" else "compat-" + suffix + "-positive")
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to(REPO / ".runtime-work"):
        raise ValueError("use fresh diagnostic output under .runtime-work")
    output.mkdir(parents=True)
    names = [*SOURCES, "config.json", "construction.json", "acquisition-provenance.json",
             *(name + ".mkv" for name in CAMERAS)]
    if suffix == "depart_conflict":
        names.append("native-conflict-history.json")
    for name in names:
        shutil.copy2(compatible / name, output / name)
    seal = {"format": "worker-sealed-capture", "provenance_kind": "synthetic_fixture",
            "diagnostic_fixture": True, "sources": {name: sha(output / name) for name in names}}
    (output / "capture-seal.json").write_text(json.dumps(seal, separators=(",", ":")) + "\n")
    if args.negative_incomplete_seal:
        del seal["sources"]["native-stop-device.json"]
        (output / "capture-seal.json").write_text(json.dumps(seal, separators=(",", ":")) + "\n")
    if args.negative:
        damaged = output / "native-stop-device.json"
        damaged.write_text(damaged.read_text().rstrip("\n") + " \n")
    result = audit(output, diagnostic_test=True)
    if result["delivery_physical_audit_passed"] or not result["diagnostic_audit_test_passed"]:
        raise ValueError("diagnostic proof incorrectly claimed Native delivery")
    try:
        _independent_review(output, seal, {})
    except ValueError as error:
        if str(error) != "independent original-frame physical review missing":
            raise
    else:
        raise ValueError("unreviewed diagnostic incorrectly passed physical review")
    print(json.dumps({"case_id": args.case, "diagnostic_audit_test_passed": True,
                      "full_camera_decode_count": len(result["camera_decode"]),
                      "unreviewed_native_rejected": True,
                      "actual_carla_capture_claimed": False}))


if __name__ == "__main__":
    main()
