"""Build three measured-risk controller fallbacks for a distinct crest exact case."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CHANGES = {
    "fallback1": ("turn = UTurnController(route)", "turn = UTurnController(route, target_speed_mps=2.0)"),
    "fallback2": ("turn = UTurnController(route)", "turn = UTurnController(route, lookahead_m=2.0)"),
    "fallback3": (
        'carla, other, site["incoming_lanes"][name]["stations"], progress[name])',
        'carla, other, site["incoming_lanes"][name]["stations"], progress[name], target_speed=5.0)'),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def build(name):
    if not name.startswith("canonical-"):
        raise ValueError("Distinct canonical crest branch name required")
    manifest_path = HERE / ("diagnostic-" + name + "-manifest.json")
    manifest = json.loads(manifest_path.read_text())
    entry = manifest["cases"][0]
    source = HERE / entry["construction"]
    if sha(source) != entry["construction_sha256"]:
        raise ValueError("Primary construction hash changed")
    primary = json.loads(source.read_text())
    if primary["case_id"] != entry["case_id"]:
        raise ValueError("Primary exact ID changed")
    definitions = json.loads((HERE / "diagnostic-curve-short-fallback-manifest.json").read_text())["cases"][0]["candidates"]
    candidates = []
    for definition in definitions:
        ident = definition["id"]
        old, new = CHANGES[ident]
        candidate = copy.deepcopy(primary)
        runner = next(row for row in candidate["files"] if row["path"] == "runner.py")
        if runner["content"].count(old) != 1:
            raise ValueError("Controller knob insertion point differs: " + ident)
        runner["content"] = runner["content"].replace(old, new)
        runner_path = source.parent / ("runner-" + ident + ".py")
        runner_path.write_text(runner["content"])
        runner["source"] = str(runner_path.relative_to(ROOT))
        candidate["candidate_engineering"] = {
            "id": ident, "changed_knob": definition["changed_knobs"][0],
            "reason": definition["trigger"]["failure_condition"],
        }
        target = source.parent / ("construction-" + ident + ".json")
        dump(target, candidate)
        candidates.append({
            "id": ident, "construction": str(target.relative_to(HERE)),
            "construction_sha256": sha(target), "trigger": definition["trigger"],
            "changed_knobs": definition["changed_knobs"],
        })
    manifest["cases"][0]["candidates"] = candidates
    output = HERE / ("diagnostic-" + name + "-fallback-manifest.json")
    dump(output, manifest)
    print(json.dumps({"case_id": entry["case_id"], "candidate_count": len(candidates),
                      "manifest": output.name, "manifest_sha256": sha(output)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    build(args.name)
