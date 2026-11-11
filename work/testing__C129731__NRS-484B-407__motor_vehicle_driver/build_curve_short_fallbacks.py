"""Build three distinct, predeclared physical-risk alternatives for one exact case."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError("Fallback runner target changed: " + old)
    return source.replace(old, new)


def build():
    base = json.loads((HERE / "construction.json").read_text())
    manifest = json.loads((HERE / "diagnostic-execution-manifest.json").read_text())
    runner = next(row["content"] for row in base["files"] if row["path"] == "runner.py")
    alternatives = [
        ("fallback1", "turn_target_speed_mps", "turn_history.jsonl",
         "measured turn overshoots exit before stable stop",
         "exit distance remains above 2 m after heading reversal and braking",
         "turn = UTurnController(route)",
         "turn = UTurnController(route, target_speed_mps=2.0)"),
        ("fallback2", "turn_lookahead_m", "turn_history.jsonl",
         "body cuts the planned return corner and fails heading reversal",
         "recorded heading change remains below 150 engineering degrees",
         "turn = UTurnController(route)",
         "turn = UTurnController(route, lookahead_m=2.0)"),
        ("fallback3", "approach_target_speed_mps", "motion_history.jsonl",
         "incoming actor has insufficient measured travel within 55 seconds",
         "either approach vehicle has no sustained approach trajectory",
         "site[\"incoming_lanes\"][name][\"stations\"], progress[name])",
         "site[\"incoming_lanes\"][name][\"stations\"], progress[name], target_speed=5.0)")]
    candidates = []
    for ident, knob, source, metric, condition, old, new in alternatives:
        changed = replace_once(runner, old, new)
        runner_source = HERE / "generated-runners" / ("runner-" + ident + ".py")
        runner_source.parent.mkdir(exist_ok=True)
        runner_source.write_text(changed)
        construction = json.loads(json.dumps(base))
        for row in construction["files"]:
            if row["path"] == "runner.py":
                row["content"] = changed
                row["source"] = str(runner_source.relative_to(REPO))
        construction["candidate_engineering"] = {"id": ident, "changed_knob": knob,
            "reason": condition}
        path = HERE / ("construction-curve-short-" + ident + ".json")
        dump(path, construction)
        candidates.append({"id": ident, "construction": path.name,
            "construction_sha256": sha(path),
            "trigger": {"source": source, "metric": metric,
                "failure_condition": condition}, "changed_knobs": [knob]})
    manifest["cases"][0]["candidates"] = candidates
    dump(HERE / "diagnostic-curve-short-fallback-manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
