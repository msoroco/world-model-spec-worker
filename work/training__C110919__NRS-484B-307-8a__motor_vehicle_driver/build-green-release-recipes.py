"""Build source-hashed synthetic red-to-green right-turn timing diagnostics."""
import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "native"))
from variant_geometry import open_drive_for


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(value):
    return [json.loads(line) for line in value.splitlines() if line.strip()]


def lines(value):
    return "".join(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n"
                   for row in value)


def main():
    manifest_path = HERE / "draft-green-release-execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    baseline = json.loads((HERE / "update015-reference-diagnostic.json").read_text())
    files = baseline["files"]
    motion_names = ("native_samples.jsonl", "trace.jsonl",
                    "capture/evidence.jsonl", "body_history.jsonl")
    originals = {name: rows(files[name]) for name in motion_names}
    if any(len(value) != 480 for value in originals.values()) or len(baseline["graphs"]) != 480:
        raise ValueError("Baseline synthetic motion must have exactly 480 graph/source rows")
    outputs = []
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        wait = suffix == "green_release_wait"
        diagnostic = copy.deepcopy(baseline)
        target = diagnostic["files"]
        samples = []
        for index in range(480):
            motion_index = min(index, 129) if wait and index <= 160 else \
                           index - 31 if wait and index > 160 else index
            native = copy.deepcopy(originals["native_samples.jsonl"][motion_index])
            current = originals["native_samples.jsonl"][index]
            native.update(native_frame=current["native_frame"], time_s=current["time_s"],
                          walker_center_xy_m=current["walker_center_xy_m"],
                          walker_conflict_occupied=current["walker_conflict_occupied"],
                          signal_state_observed="Red" if index < 160 else "Green")
            if wait and 130 <= index <= 160:
                native["speed_mps"] = 0.0
            samples.append(native)
            trace = copy.deepcopy(originals["trace.jsonl"][motion_index])
            trace.update(frame=current["native_frame"], time_s=current["time_s"],
                         speed_mps=native["speed_mps"],
                         speed_mph=native["speed_mps"] * 2.2369362921)
            target.setdefault("_green_trace", []).append(trace)
            evidence = copy.deepcopy(originals["capture/evidence.jsonl"][motion_index])
            current_evidence = originals["capture/evidence.jsonl"][index]
            evidence.update(original_frame=current_evidence["original_frame"],
                            recording_time_s=current_evidence["recording_time_s"],
                            replay_frame=current_evidence["replay_frame"],
                            replay_simulation_time_s=current_evidence["replay_simulation_time_s"])
            evidence["ego"]["speed_mps"] = native["speed_mps"]
            target.setdefault("_green_evidence", []).append(evidence)
            body = copy.deepcopy(originals["body_history.jsonl"][motion_index])
            body.update(frame=current["native_frame"], time_s=current["time_s"])
            target.setdefault("_green_body", []).append(body)
            graph = diagnostic["graphs"][index]
            source_graph = baseline["graphs"][motion_index]
            graph["nodes"] = copy.deepcopy(source_graph["nodes"])
        target["native_samples.jsonl"] = lines(samples)
        target["trace.jsonl"] = lines(target.pop("_green_trace"))
        target["capture/evidence.jsonl"] = lines(target.pop("_green_evidence"))
        target["body_history.jsonl"] = lines(target.pop("_green_body"))
        geometry = json.loads(target["road_geometry.json"])
        geometry.update(stopping_reference_kind="marked_stop_line",
                        stopping_reference_y_m=-14.0,
                        signal_schedule_authored={"red_frames": 160, "green_from_frame": 160},
                        native_signal_transition_verified=False)
        target["road_geometry.json"] = json.dumps(geometry) + "\n"
        target["context.json"] = json.dumps({"surveyed_right_turn": geometry}) + "\n"
        target["road.xodr"] = open_drive_for(suffix)
        capture = json.loads(target["capture/manifest.json"])
        capture["sources"]["road.xodr"] = hashlib.sha256(target["road.xodr"].encode()).hexdigest()
        capture["sources"]["trace.jsonl"] = hashlib.sha256(target["trace.jsonl"].encode()).hexdigest()
        target["capture/manifest.json"] = json.dumps(capture) + "\n"
        path = HERE / f"update026-{suffix}-diagnostic.json"
        path.write_text(json.dumps(diagnostic, separators=(",", ":"), allow_nan=False) + "\n")
        if path.stat().st_size >= 2 * 1024 * 1024:
            raise ValueError("Green-release diagnostic exceeds return limit")
        relative = path.relative_to(ROOT).as_posix()
        digest = sha(path)
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "diagnostic-input.json", "source": relative,
                               "sha256": digest}],
                  "generator": {"source": relative, "sha256": digest}}
        recipe_path = HERE / f"update026-{suffix}-recipe.json"
        recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
        entry["fixture_recipe"] = recipe_path.relative_to(ROOT).as_posix()
        outputs.append({"case_id": entry["case_id"], "diagnostic_sha256": digest,
                        "recipe_sha256": sha(recipe_path), "bytes": path.stat().st_size})
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    summary = {"format": "c110919-green-release-recipes-v1",
               "manifest_sha256": sha(manifest_path), "cases": outputs,
               "synthetic_diagnostic": True, "selected": False}
    path = HERE / "update026-green-recipe-summary.json"
    path.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"cases": len(outputs), "manifest_sha256": sha(manifest_path),
                      "recipe_summary_sha256": sha(path)}))


if __name__ == "__main__":
    main()
