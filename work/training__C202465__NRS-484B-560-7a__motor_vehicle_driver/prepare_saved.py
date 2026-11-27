"""Stage public diagnostic acquisition only for recorded-only processing."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from worker_exchange.runtime_cli import materialize


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    for name in ("manifest", "case", "public", "attempt"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    public = Path(args.public).resolve()
    attempt = Path(args.attempt).resolve()
    manifest = Path(args.manifest).resolve()
    receipt = json.loads((public / "compatibility.json").read_text())
    if receipt.get("case_id") != args.case or receipt.get("passed") is not True:
        raise ValueError("Public compatibility receipt differs")
    materialize(manifest, args.case, attempt, "primary")
    copied = 0
    camera_names = ("overview", "approach", "reference_corner", "driver_reference")
    for name, digest in receipt["fixture_manifest"].items():
        source, target = public / name, attempt / name
        if name in (camera + ".mkv" for camera in camera_names):
            receipts = [json.loads((public / f"source-{index}.json").read_text())
                        for index in range(len(camera_names))]
            actual = sha(source)
            if actual not in [item.get("video_sha256") for item in receipts]:
                raise ValueError("No decoded source receipt for " + name)
            digest = actual
        if sha(source) != digest or target.exists():
            raise ValueError("Fixture source changed or shadows materialization: " + name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1
    print(json.dumps({"case_id": args.case, "sources": copied,
                      "recorded_only": True, "original_native_executed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
