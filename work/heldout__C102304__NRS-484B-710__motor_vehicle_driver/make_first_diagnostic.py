"""Create a case-specific textual software diagnostic from the pinned schema seed.

The seed supplies only Native-shaped trace/graph structure and four synthetic
videos. Fire distance, participant state and dispatch context below are newly
authored inputs for testing this finalizer; none is physical evidence.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + "__traveling_follow_500ft"


def lines(rows):
    return "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)


def box(x0, x1, y):
    return [[x0, y-1], [x1, y-1], [x1, y+1], [x0, y+1]]


def main():
    spec = json.loads((ROOT / "runtime/fixtures/example.json").read_text())
    files = spec["files"]
    mapping = [json.loads(s) for s in files["video_frames.jsonl"].splitlines()]
    trace = [json.loads(s) for s in files["trace.jsonl"].splitlines()]
    if len(mapping) != len(trace) or len(mapping) != 9:
        raise ValueError("Pinned schema seed changed")
    feet_per_metre = 3.280839895013123
    footprints, state = [], []
    for frame, point in zip(mapping, trace):
        if frame["carla_frame"] != point["frame"] or frame["time_s"] != point["time_s"]:
            raise ValueError("Schema seed frame identity changed")
        x, y = point["position"]["x"], point["position"]["y"]
        apparatus_near = x + 2 + 500 / feet_per_metre
        footprints.append({
            "frame": point["frame"], "time_s": point["time_s"],
            "ego_id": "ego", "apparatus_id": "apparatus",
            "ego_corners": box(x-2, x+2, y),
            "apparatus_corners": box(apparatus_near, apparatus_near+6, y),
        })
        state.append({
            "frame": point["frame"], "time_s": point["time_s"],
            "apparatus_moving": True, "ego_moving": True,
            "ego_following": True, "ego_parked": False,
            "warning_lamp": True, "siren": None,
        })
    files["participant_footprints.jsonl"] = lines(footprints)
    files["participant_state.jsonl"] = lines(state)
    config = json.loads((HERE / "config.json").read_text())
    files["fire_context.json"] = json.dumps(config["fire_context"], indent=2) + "\n"
    manifest = json.loads(files["capture/manifest.json"])
    manifest["case_id"] = CASE
    manifest["source_run"] = "synthetic-fire-distance-software-diagnostic"
    manifest["required_observations"] = config["required_atoms"]
    files["capture/manifest.json"] = json.dumps(manifest, indent=2) + "\n"
    files["fixture-provenance.json"] = json.dumps({
        "scope": "Synthetic software diagnostic; original schema seed supplies graph and trace shape only.",
        "case_id": CASE,
        "fire_measurement_source": "participant_footprints.jsonl and participant_state.jsonl in this diagnostic",
        "physical_evidence": False,
    }, indent=2) + "\n"
    # Remove the speed-law example's measurements and context. Native graph and
    # trace shapes remain only to exercise the frozen converter/renderer.
    for key in ("alley_context.json", "body_history.jsonl", "speed_samples.jsonl"):
        files.pop(key, None)
    spec_path = HERE / "diagnostic-input.json"
    spec_path.write_text(json.dumps(spec, separators=(",", ":")) + "\n")
    relative = spec_path.relative_to(ROOT).as_posix()
    digest = sha256(spec_path.read_bytes()).hexdigest()
    recipe = {"format": "worker-fixture-recipe",
              "sources": [{"path": "diagnostic-input.json", "source": relative,
                           "sha256": digest}],
              "generator": {"source": relative, "sha256": digest}}
    (HERE / "diagnostic-recipe.json").write_text(json.dumps(recipe, indent=2) + "\n")


if __name__ == "__main__":
    main()
