"""Exercise exact selected recorded-only processing and missing-device feedback."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
ROOT = FOLDER.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def call(*args):
    result = subprocess.run([sys.executable, "-B", str(ROOT / "runtime.py"),
        *map(str, args)], cwd=ROOT, capture_output=True, text=True, timeout=900)
    if result.returncode:
        raise ValueError(result.stdout[-1000:] + result.stderr[-3000:])
    return result


def run(letter, validator):
    action, condition = (letter.split("-", 1) if "-" in letter else ("park", letter))
    suffix = "" if action == "park" else action + "_"
    case = FOLDER.name + "__selected_03f318de__" + suffix + "condition_" + condition
    prefix = "selected-" + letter
    scratch = ROOT / ".runtime-work"
    manifest = FOLDER / "selected-compat-manifest.json"
    with tempfile.TemporaryDirectory(dir=scratch, prefix="c385967-saved-" + letter + "-") as name:
        temporary = Path(name)
        fixture, attempt, output = (temporary / part for part in
                                    ("source", "attempt", "processed"))
        call("fixture", "--recipe", HERE / f"{prefix}-fixture-recipe.json",
             "--output", fixture)
        call("offline", "--manifest", manifest, "--case", case, "--output", attempt)
        for item in fixture.iterdir():
            target = attempt / item.name
            if target.exists():
                raise ValueError("Fixture shadows selected construction: " + item.name)
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copyfile(item, target)
        # The fixture is a synthetic diagnostic, not an operator-selected Native run.
        (attempt / "candidate-selection.json").unlink()
        call("process-saved", "--manifest", manifest, "--case", case,
             "--attempt", attempt, "--output", output,
             "--library", ROOT / "runtime/library", "--validator", validator)
        positive = json.loads((output / "v0001/processing.json").read_text())
        if not (positive.get("passed") is True and positive.get("recorded_only") is True
                and positive.get("missing_evidence") is False
                and positive.get("timestamp_joins", {}).get("frames") == 600
                and positive.get("final_video_checks", {}).get("frames") == 600):
            raise ValueError("Selected recorded-only positive incomplete")
        positive_path = HERE / f"{prefix}-saved-processing.json"
        positive_path.write_text(json.dumps(positive, indent=2) + "\n")
        negative_attempt = temporary / "negative-attempt"
        shutil.copytree(attempt, negative_attempt)
        (negative_attempt / "official_device.json").unlink()
        negative_output = temporary / "negative-processed"
        call("process-saved", "--manifest", manifest, "--case", case,
             "--attempt", negative_attempt, "--output", negative_output,
             "--library", ROOT / "runtime/library", "--validator", validator)
        feedback = json.loads((negative_output / "v0001/feedback.json").read_text())
        rejected = json.loads((negative_output / "v0001/processing.json").read_text())
        if not (feedback.get("recorded_only") is True and
                feedback.get("native_replay_requested") is False and
                "Missing required source: official_device.json" in feedback.get("error", "") and
                rejected.get("missing_evidence") is True):
            raise ValueError("Selected missing-device feedback incomplete")
        negative_path = HERE / f"{prefix}-saved-negative-feedback.json"
        negative_path.write_text(json.dumps(feedback, indent=2) + "\n")
        return {"case_id": case, "recorded_only": True,
                "positive_processing_sha256": sha(positive_path),
                "negative_feedback_sha256": sha(negative_path),
                "diagnostic_fixture": True, "original_native_executed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", choices=("a", "b", "stop-a", "stop-b", "stand-a", "stand-b"), required=True)
    parser.add_argument("--validator", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.condition, args.validator.resolve()), sort_keys=True))
