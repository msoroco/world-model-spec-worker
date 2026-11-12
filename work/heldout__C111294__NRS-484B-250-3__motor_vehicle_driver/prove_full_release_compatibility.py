"""Attach complete release diagnostics and rerun every affected exact candidate."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from time import time_ns

from build_full_release_diagnostic import expand


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
VALIDATOR = ROOT / ".runtime-work/fire-decoder/.lake/build/bin/adapterCheck"


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def prove():
    generated = ROOT / ".runtime-work" / ("c111294-full-release-" + str(time_ns()))
    summaries = expand(generated)
    for rank in range(3):
        short = f"yield_release_delay-{rank:04d}"
        shutil.copyfile(generated / f"{short}-candidate.json",
                        HERE / f"diagnostic-yield-sweep-{rank:04d}.json")
        source = HERE / f"diagnostic-yield-sweep-{rank:04d}.json"
        recipe_path = HERE / f"diagnostic-recipe-yield-sweep-{rank:04d}.json"
        recipe = json.loads(recipe_path.read_text())
        recipe["generator"]["sha256"] = digest(source)
        for item in recipe["sources"]:
            if item["source"] == str(source.relative_to(ROOT)):
                item["sha256"] = digest(source)
        write(recipe_path, recipe)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        if "__yield_release_delay-" not in entry["case_id"]:
            continue
        short = entry["case_id"].rsplit("__", 1)[-1]
        for candidate, target in [("primary", entry)] + [
            (item["id"], item) for item in entry["candidates"]]:
            label = short + "-full-window-" + candidate
            output = ROOT / ".runtime-work" / (label + "-compat-" + str(time_ns()))
            command = [sys.executable, str(ROOT / "runtime.py"), "compatibility",
                       "--manifest", str(MANIFEST), "--case", entry["case_id"],
                       "--output", str(output), "--library", str(ROOT / "runtime/library"),
                       "--validator", str(VALIDATOR)]
            if candidate != "primary":
                command += ["--candidate", candidate]
            run = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            if run.returncode:
                (HERE / (label + "-failure.log")).write_text(run.stdout + run.stderr)
                raise ValueError(label + " compatibility failed; see retained failure log")
            receipt = HERE / (label + "-compatibility.json")
            write(receipt, json.loads(run.stdout))
            analysis = HERE / (label + "-analysis.log")
            negative = HERE / (label + "-negative.log")
            shutil.copyfile(output / "compatibility-analysis.log", analysis)
            shutil.copyfile(output / "negative-analysis.log", negative)
            target["compatibility"] = {"receipt": receipt.name,
                                       "sha256": digest(receipt),
                                       "log": analysis.name,
                                       "negative_log": negative.name}
            if candidate == "primary":
                entry["negative"] = {"log": negative.name}
            write(MANIFEST, manifest)
            print(label + " compatibility=0", flush=True)
    return summaries


if __name__ == "__main__":
    print(json.dumps(prove(), indent=2))
