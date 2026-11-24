"""Retain the compact receipts from exact selected-manifest CPU runs."""

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parents[1] / ".runtime-work/c131364-selected"
OUT = ROOT / "selected-v2/proofs"


def main():
    for witness in (1, 2):
        for candidate in ("primary", "fallback1"):
            name = f"witness{witness}-{candidate}"
            compat_dir = SCRATCH / ("witness1-compat" if witness == 1 and candidate == "primary" else name + "-compat")
            saved_dir = SCRATCH / ("witness1-saved" if witness == 1 and candidate == "primary" else name + "-saved")
            offline_dir = SCRATCH / ("witness1-offline" if witness == 1 and candidate == "primary" else name + "-offline")
            target = OUT / name
            target.mkdir(parents=True, exist_ok=True)
            for source, destination in (
                (compat_dir / "compatibility.json", "compatibility.json"),
                (compat_dir / "negative-analysis.log", "negative-analysis.log"),
                (saved_dir / "v0001/processing.json", "processing.json"),
                (offline_dir / "offline.log", "offline.log"),
            ):
                if not source.is_file():
                    raise FileNotFoundError(source)
                shutil.copyfile(source, target / destination)
    print("collected four exact selected primary/fallback receipt sets")


if __name__ == "__main__":
    main()
