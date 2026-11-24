"""Add original diagnostic velocity vectors for the current renderer overlay."""
import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = ("witness_1", "witness_2", "exception_1_1", "exception_1_2")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for case in CASES:
    folder = HERE / "long-capture-matrix" / case
    generator_path = folder / "diagnostic-generator.json"
    generator = json.loads(generator_path.read_text())
    trace = [json.loads(line) for line in generator["files"]["trace.jsonl"].splitlines()]
    if len(trace) != 600:
        raise ValueError("Expected exact 600-frame trace: " + case)
    for row in trace:
        speed = float(row["speed_mps"])
        angle = math.radians(float(row["heading_deg"]))
        row["velocity_mps"] = [speed * math.cos(angle), speed * math.sin(angle), 0.0]
    trace_text = "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in trace)
    generator["files"]["trace.jsonl"] = trace_text
    capture = json.loads(generator["files"]["capture/manifest.json"])
    capture["sources"]["trace.jsonl"] = hashlib.sha256(trace_text.encode()).hexdigest()
    generator["files"]["capture/manifest.json"] = json.dumps(capture, separators=(",", ":")) + "\n"
    generator_path.write_text(json.dumps(generator, separators=(",", ":")) + "\n")
    if generator_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Diagnostic generator exceeds returned file limit")
    recipe_path = folder / "diagnostic-recipe.json"
    recipe = json.loads(recipe_path.read_text())
    recipe["generator"]["sha256"] = sha(generator_path)
    recipe_path.write_text(json.dumps(recipe, separators=(",", ":")) + "\n")
    print(case, sha(generator_path), sha(recipe_path))
