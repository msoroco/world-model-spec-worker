"""Exercise all three 700-frame C104496 textual source recipes and media."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work/c104496-fixture-proof-v7"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path: Path) -> int:
    return sum(1 for _ in path.open())


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    rows = []
    for suffix in ("probe_01", "probe_02", "probe_03"):
        recipe = HERE / "source-fixture" / suffix / "recipe.json"
        target = SCRATCH / suffix
        env = dict(os.environ, TMPDIR=str(SCRATCH),
                   SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
                   PYTHONDONTWRITEBYTECODE="1")
        command = [sys.executable, str(ROOT / "runtime.py"), "fixture",
                   "--recipe", str(recipe), "--output", str(target)]
        run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                             text=True, timeout=300)
        if run.returncode:
            raise RuntimeError(suffix + " fixture: " + run.stderr[-1200:])
        receipt = json.loads(run.stdout)
        if receipt["recipe_sha256"] != sha(recipe) or len(receipt["fixture_manifest"]) < 709:
            raise ValueError("source recipe or 700 graph output differs")
        for name in ("trace.jsonl", "video_frames.jsonl",
                     "turn_history.jsonl", "analytic_sight.jsonl",
                     "capture/evidence.jsonl", "capture/native/frames.jsonl"):
            if lines(target / name) != 700:
                raise ValueError("700-frame source join differs: " + name)
        media = []
        for name in VIEWS:
            path = target / (name + ".mkv")
            probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                                    "-select_streams", "v:0", "-show_entries",
                                    "stream=width,height,nb_read_frames",
                                    "-of", "json", str(path)], capture_output=True,
                                   text=True, timeout=120)
            if probe.returncode:
                raise RuntimeError("source video probe failed: " + name)
            stream = json.loads(probe.stdout)["streams"][0]
            size = [1920, 1080] if name == "overview" else [1280, 720]
            if [stream["width"], stream["height"]] != size or stream["nb_read_frames"] != "700":
                raise ValueError("four-view source profile changed: " + name)
            decode = subprocess.run(["ffmpeg", "-nostdin", "-v", "error",
                                     "-i", str(path), "-f", "null", "-"],
                                    capture_output=True, text=True, timeout=180)
            if decode.returncode:
                raise RuntimeError("source video full decode failed: " + name)
            media.append({"view": name, "frames": 700,
                          "source_sha256": sha(path), "full_decode_exit_code": 0})
        rows.append({"case_id": HERE.name + "__" + suffix,
                     "recipe_sha256": sha(recipe),
                     "fixture_sha256": receipt["fixture_sha256"],
                     "source_frames": 700, "views": media,
                     "original_pixels_claimed": False})
        print(json.dumps({"completed": suffix, "views": len(media)}), flush=True)
    proof = {"format": "c104496-case-source-fixture-proof-v1",
             "assignment_id": HERE.name, "cases": rows,
             "passed": len(rows) == 3,
             "physical_visibility_or_reversal_proven": False}
    path = HERE / "source-fixture-proof.json"
    path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": proof["passed"], "proof_sha256": sha(path)}))


if __name__ == "__main__":
    main()
