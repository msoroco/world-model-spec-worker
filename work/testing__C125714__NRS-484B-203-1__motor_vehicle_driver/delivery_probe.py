"""Exercise the independent audit on labeled CPU fixture sources."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from delivery_audit import audit

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work" / "c125714-2031" / "delivery-probe"


def run(case, negative=False):
    if not case.startswith(HERE.name + "__"):
        raise ValueError("wrong exact delivery case")
    variant = case.split("__")[-1]
    if variant not in ("right_half", "wrong_side", "left_encroachment", "right_constrained"):
        raise ValueError("unknown exact delivery variant")
    root = SCRATCH / variant / ("negative" if negative else "positive")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    fixture, attempt = root / "fixture", root / "attempt"
    manifest = HERE / "manifest.draft.json"
    recipe = HERE / "cases" / variant / "fixture-recipe.json"
    subprocess.run([sys.executable, str(REPO / "runtime.py"), "fixture",
                    "--recipe", str(recipe), "--output", str(fixture)],
                   check=True, cwd=REPO, env=os.environ, capture_output=True, text=True)
    subprocess.run([sys.executable, str(REPO / "runtime.py"), "materialize",
                    "--manifest", str(manifest), "--case", case, "--output", str(attempt)],
                   check=True, cwd=REPO, env=os.environ, capture_output=True, text=True)
    for source in fixture.iterdir():
        target = attempt / source.name
        if target.exists():
            raise ValueError("fixture shadows selected construction")
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copyfile(source, target)
    subprocess.run([sys.executable, str(attempt / "analysis.py"), "--attempt", str(attempt),
                    "--output", str(attempt / "analysis-report.json")],
                   check=True, cwd=attempt, env=os.environ, capture_output=True, text=True)
    if negative:
        camera = attempt / "opposing-camera-frames" / "camera-manifest.json"
        camera.write_text(camera.read_text() + "\n")
    return audit(attempt, case, diagnostic=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.negative), sort_keys=True))


if __name__ == "__main__":
    main()
