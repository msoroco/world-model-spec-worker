"""Build 480-frame synthetic source diagnostics for the unselected yield pair."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE / "update015-reference-diagnostic.json"
MANIFEST = HERE / "draft-yield-branch-execution-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def lines(items):
    return "".join(json.dumps(item, separators=(",", ":"), allow_nan=False) + "\n"
                   for item in items)


def main():
    manifest = json.loads(MANIFEST.read_text())
    baseline = json.loads(BASE.read_text())
    source = {name: rows(baseline["files"][name]) for name in
              ("native_samples.jsonl", "trace.jsonl", "capture/evidence.jsonl",
               "body_history.jsonl")}
    if any(len(group) != 480 for group in source.values()) or len(baseline["graphs"]) != 480:
        raise ValueError("Exact baseline diagnostic interval missing")
    output = []
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        if suffix not in ("yield_wait", "yield_conflict_entry"):
            raise ValueError("Unexpected exact yield case")
        wait = suffix == "yield_wait"
        diagnostic = copy.deepcopy(baseline)
        files = diagnostic["files"]
        groups = {name: [] for name in source}
        for index in range(480):
            motion_index = (220 if wait and 220 <= index <= 260 else
                            index - 40 if wait and index > 260 else index)
            current = source["native_samples.jsonl"][index]
            native = copy.deepcopy(source["native_samples.jsonl"][motion_index])
            occupied = 220 <= index <= 260
            native.update(native_frame=current["native_frame"], time_s=current["time_s"],
                          walker_center_xy_m=[10.0, 0.0 if occupied else 5.0],
                          walker_conflict_occupied=occupied,
                          signal_state_observed="Red", yield_policy=suffix,
                          yield_decision_reason=("pedestrian_conflict_occupied" if wait and occupied
                                                 else "deliberate_conflict_entry_probe" if occupied
                                                 else "conflict_clear"))
            if wait and 220 <= index <= 260:
                native["speed_mps"] = 0.0
                native["controller_request"] = {"throttle": 0.0, "brake": 1.0,
                                                "steer": 0.0, "hand_brake": True}
            groups["native_samples.jsonl"].append(native)
            trace = copy.deepcopy(source["trace.jsonl"][motion_index])
            trace.update(frame=current["native_frame"], time_s=current["time_s"],
                         speed_mps=native["speed_mps"],
                         speed_mph=native["speed_mps"] * 2.2369362921)
            groups["trace.jsonl"].append(trace)
            evidence = copy.deepcopy(source["capture/evidence.jsonl"][motion_index])
            current_evidence = source["capture/evidence.jsonl"][index]
            evidence.update(original_frame=current_evidence["original_frame"],
                            recording_time_s=current_evidence["recording_time_s"],
                            replay_frame=current_evidence["replay_frame"],
                            replay_simulation_time_s=current_evidence["replay_simulation_time_s"])
            evidence["ego"]["speed_mps"] = native["speed_mps"]
            groups["capture/evidence.jsonl"].append(evidence)
            body = copy.deepcopy(source["body_history.jsonl"][motion_index])
            body.update(frame=current["native_frame"], time_s=current["time_s"])
            groups["body_history.jsonl"].append(body)
            diagnostic["graphs"][index]["nodes"] = copy.deepcopy(
                baseline["graphs"][motion_index]["nodes"])
        for name, values in groups.items():
            files[name] = lines(values)
        capture = json.loads(files["capture/manifest.json"])
        capture["sources"]["trace.jsonl"] = hashlib.sha256(
            files["trace.jsonl"].encode()).hexdigest()
        files["capture/manifest.json"] = json.dumps(capture) + "\n"
        target = HERE / "yield_branch_cases" / f"{suffix}-diagnostic.json"
        target.write_text(json.dumps(diagnostic, separators=(",", ":"), allow_nan=False) + "\n")
        if target.stat().st_size >= 2 * 1024 * 1024:
            raise ValueError("Returned diagnostic exceeds 2 MiB")
        relative = target.relative_to(ROOT).as_posix()
        digest = sha(target)
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "diagnostic-input.json", "source": relative,
                               "sha256": digest}],
                  "generator": {"source": relative, "sha256": digest}}
        recipe_path = target.with_name(f"{suffix}-recipe.json")
        recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
        entry["fixture_recipe"] = recipe_path.relative_to(ROOT).as_posix()
        output.append({"case_id": entry["case_id"], "diagnostic_sha256": digest,
                       "recipe_sha256": sha(recipe_path), "bytes": target.stat().st_size})
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    summary = {"format": "c110919-yield-branch-recipes-v1",
               "manifest_sha256": sha(MANIFEST), "cases": output,
               "synthetic_diagnostic": True, "canonical_selected": False}
    target = HERE / "yield_branch_cases/recipe-summary.json"
    target.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"cases": len(output), "manifest_sha256": sha(MANIFEST),
                      "summary_sha256": sha(target)}))


if __name__ == "__main__":
    main()
