"""Build exact CPU construction variants for the two heavy-lane judgment grids.

This stages construction inputs only. A staged variant is not a delivered case
until its exact fallback, saved-processing, physical, and comparison proofs pass.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
from batch_pipeline.sweeps import grid
from worker_exchange.candidate_constructions import validate as validate_candidates
from worker_exchange.identity_preflight import validate as validate_identity
from worker_exchange.fixture_generator import generate as generate_fixture


SOURCE_CASES = {
    HERE.name + "__heavy_passing_plan": "passing_boundary_crossing",
    HERE.name + "__heavy_turn_plan": "lawful_turn_preparation_boundary_crossing",
}


def _variant(source: dict, old_case: str, new_case: str, setpoint_m: float) -> dict:
    """Retain the source case's full implementation, changing identity and target."""
    if not isinstance(setpoint_m, (int, float)) or not 0 <= setpoint_m <= 2.2:
        raise ValueError("Sweep setpoint is outside the authored engineering grid")

    def replace(value):
        if isinstance(value, str):
            return value.replace(old_case, new_case)
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        return value

    result = replace(deepcopy(source))
    if result["case_id"] != new_case:
        raise ValueError("Source construction identity differs")
    configs = [item for item in result["files"] if item["path"] == "config.json"]
    if len(configs) != 1:
        raise ValueError("Exact construction needs one config.json")
    config = json.loads(configs[0]["content"])
    if config["selected_case_id"] != new_case or config["case"]["case_id"] != new_case:
        raise ValueError("Constructed configuration selected another case")
    if config["supported_case_ids"] != [new_case]:
        raise ValueError("Constructed runner supports another case")
    config["engineering"]["lateral_offset_m"] = float(setpoint_m)
    configs[0]["content"] = json.dumps(config, indent=2) + "\n"
    runners = [item for item in result["files"] if item["path"] == "runner.py"]
    if len(runners) != 1:
        raise ValueError("Exact construction needs one runner.py")
    positive_only = "or not isfinite(value) or value <= 0:"
    nonnegative_lateral = ("or not isfinite(value) or "
                           "(value < 0 if key == 'lateral_offset_m' else value <= 0):")
    if runners[0]["content"].count(positive_only) != 1:
        raise ValueError("Selected runner knob validation changed")
    runners[0]["content"] = runners[0]["content"].replace(
        positive_only, nonnegative_lateral, 1)
    runner = runners[0]["content"]
    anchor = '    frame_map = FrameMap(output / "video_frames.jsonl")\n'
    if runner.count(anchor) != 1:
        raise ValueError("Sweep frame-map source changed")
    runner = runner.replace(anchor, anchor +
        '        setpoint_source = (output / "lateral_control_setpoint_source.jsonl").open("w")\n')
    anchor = '            frame_map.append(frame, time_s)\n'
    if runner.count(anchor) != 1:
        raise ValueError("Sweep frame source changed")
    runner = runner.replace(anchor, anchor +
        '            setpoint_source.write(json.dumps({"frame": frame, "time_s": time_s, '
        '"lateral_control_setpoint_m": engineering["lateral_offset_m"]}) + "\\n")\n')
    anchor = '        if frame_map is not None:\n'
    if runner.count(anchor) != 1:
        raise ValueError("Sweep source close changed")
    runner = runner.replace(anchor, '        setpoint_source.close()\n' + anchor)
    runners[0]["content"] = runner
    finalizers = [item for item in result["files"] if item["path"] == "heavy_lane_finalizer.py"]
    if len(finalizers) != 1:
        raise ValueError("Exact construction needs one finalizer")
    finalizer = finalizers[0]["content"]
    anchor = '    video_hashes = {name: _required(root, name)[1] for name in CAMERA_FILES}\n'
    if finalizer.count(anchor) != 1:
        raise ValueError("Sweep finalizer source changed")
    finalizer = finalizer.replace(anchor, anchor +
        '    setpoint_path, setpoint_sha = _required(root, "lateral_control_setpoint_source.jsonl")\n')
    anchor = '    surveyed = {(lane["road_id"], lane["lane_id"]) for lane in survey["lanes"]}\n'
    if finalizer.count(anchor) != 1:
        raise ValueError("Sweep finalizer frame join changed")
    finalizer = finalizer.replace(anchor,
        '    setpoints = _rows(setpoint_path)\n'
        '    if len(setpoints) != len(frames) or any(\n'
        '            row.get("frame") != frame.get("carla_frame") or\n'
        '            row.get("time_s") != frame.get("time_s") or\n'
        '            row.get("lateral_control_setpoint_m") != config["engineering"]["lateral_offset_m"]\n'
        '            for row, frame in zip(setpoints, frames)):\n'
        '        raise ValueError("Captured lateral setpoint source differs from selected frames or control")\n'
        + anchor)
    anchor = '    values = {\n'
    if finalizer.count(anchor) != 1:
        raise ValueError("Sweep derived values changed")
    finalizer = finalizer.replace(anchor, anchor +
        '        "lateral_control_setpoint_m": [row["lateral_control_setpoint_m"] for row in setpoints],\n')
    anchor = '    return {"case_id": CASE,\n'
    if finalizer.count(anchor) != 1:
        raise ValueError("Sweep result source changed")
    finalizer = finalizer.replace(anchor,
        '    setpoint = _rows(root / "lateral_control_setpoint_source.jsonl")[0]["lateral_control_setpoint_m"]\n'
        + anchor)
    anchor = '            "realized_observables": {"heavy_lane_minimum_clearance_m": {\n'
    if finalizer.count(anchor) != 1:
        raise ValueError("Sweep observable summary changed")
    finalizer = finalizer.replace(anchor,
        '            "realized_observables": {"lateral_control_setpoint_m": {\n'
        '                "unit": "m", "method": "authored Native lateral control setpoint, recorded separately from source-measured body clearance",\n'
        '                "time_window": "selected 160-frame capture", "statistic": "first",\n'
        '                "reference": "lateral_control_setpoint_m.jsonl", "value": setpoint,\n'
        '                "sample_window_s": [measurement["frames"][0]["time_s"],\n'
        '                                    measurement["frames"][-1]["time_s"]]},\n'
        '                "heavy_lane_minimum_clearance_m": {\n')
    finalizers[0]["content"] = finalizer
    tests = [item for item in result["files"] if item["path"] == "tests/test_heavy_lane_source.py"]
    if tests:
        if len(tests) != 1:
            raise ValueError("Exact construction needs one source test")
        test = tests[0]["content"]
        anchor = '        for name in finalizer.CAMERA_FILES:\n'
        if test.count(anchor) != 1:
            raise ValueError("Sweep saved-source test changed")
        test = test.replace(anchor,
            '        setpoint = json.loads((self.root / "config.json").read_text())["engineering"]["lateral_offset_m"]\n'
            '        (self.root / "lateral_control_setpoint_source.jsonl").write_text("".join(\n'
            '            json.dumps({"frame": 20 + index, "time_s": index / 20,\n'
            '                        "lateral_control_setpoint_m": setpoint}) + "\\n"\n'
            '            for index in range(160)))\n'
            + anchor)
        test = test.replace('self.assertEqual(len(result["recording_evidence"]), 6)',
                            'self.assertEqual(len(result["recording_evidence"]), 7)')
        tests[0]["content"] = test
    description = config["case"]["recording_description"]
    description["channels"].append({
        "name": "lateral_control_setpoint_m", "unit": "m", "sampling_rate_hz": 20,
        "method": "Captured lateral control target for each original Native frame.",
        "time_window": "original 160-frame capture",
        "reference_frame": "source-surveyed Native three-lane road",
        "uncertainty": "authored control target is separate from measured physical clearance",
    })
    result["recording_description"] = deepcopy(description)
    configs[0]["content"] = json.dumps(config, indent=2) + "\n"
    validate_identity(result, result["law_id"], result["cell_id"])
    for item in result["files"]:
        if item["path"].endswith(".py"):
            compile(item["content"], new_case + "/" + item["path"], "exec")
    return result


def diagnostic_at_setpoint(source: dict, setpoint_m: float) -> dict:
    """Move the synthetic ego consistently across trace, body and capture packets.

    The source remains a diagnostic fixture. Its graph observations are copied
    from the transformed capture observations, so no Native acquisition is
    implied by this transformation.
    """
    if setpoint_m not in (0.0, 1.1, 2.2):
        raise ValueError("Setpoint is not in the authored judgment grid")
    result = deepcopy(source)
    files = result["files"]
    trace = [json.loads(line) for line in files["trace.jsonl"].splitlines()]
    body = [json.loads(line) for line in files["heavy_lane_sources.jsonl"].splitlines()]
    evidence = [json.loads(line) for line in files["capture/evidence.jsonl"].splitlines()]
    if not len(trace) == len(body) == len(evidence) == 9:
        raise ValueError("Diagnostic sources must have nine joined frames")
    first = trace[0]["position"]
    last = trace[-1]["position"]
    heading = body[0]["lane"]["heading_xy"]
    right = (heading[1], -heading[0])
    source_extent = sum((last[k] - first[k]) * axis for k, axis in zip(("x", "y"), right))
    if source_extent <= 0.1:
        raise ValueError("Selected source lacks rightward motion")
    graphs = {item["path"]: item for item in result["graphs"]}
    for motion, observation, capture in zip(trace, body, evidence):
        if not motion["frame"] == observation["frame"] == capture["original_frame"]:
            raise ValueError("Diagnostic source frame join changed")
        position = motion["position"]
        old_xy = (position["x"], position["y"])
        current = sum((position[k] - first[k]) * axis for k, axis in zip(("x", "y"), right))
        change = setpoint_m * current / source_extent - current
        dx, dy = (change * right[0], change * right[1])
        position["x"] += dx
        position["y"] += dy
        motion["position_m"][0] += dx
        motion["position_m"][1] += dy
        for component in observation["heavy_vehicle_components"]:
            for corner in component["corners_xy_m"]:
                corner[0] += dx
                corner[1] += dy
        ego = capture["ego"]
        if any(abs(ego["position_m"][i] - old_xy[i]) > 1e-5 for i in (0, 1)):
            raise ValueError("Capture ego differs from trace source")
        ego["position_m"][0] += dx
        ego["position_m"][1] += dy
        for corner in ego["body_vertices_m"]:
            corner[0] += dx
            corner[1] += dy
        observed = capture["original_observations"]
        for participant in observed["participants"]:
            if participant["actor_id"] == capture["actor_id"]:
                participant["position_m"][0] += dx
                participant["position_m"][1] += dy
                for corner in participant["body_vertices_m"]:
                    corner[0] += dx
                    corner[1] += dy
        for camera in observed["rgb_sensors"]:
            if camera["parent_actor_id"] == capture["actor_id"]:
                camera["position_m"][0] += dx
                camera["position_m"][1] += dy
        frame = capture["original_frame"]
        for kind in ("abstract", "base"):
            graph_path = f"capture/native/graphs/{kind}/{frame:08d}.adapter.json"
            if graph_path not in graphs:
                raise ValueError("Missing graph observation packet")
            graphs[graph_path]["attributes"]["observed_evidence"] = deepcopy(observed)
    files["trace.jsonl"] = "".join(json.dumps(row, allow_nan=False) + "\n" for row in trace)
    files["heavy_lane_sources.jsonl"] = "".join(json.dumps(row, allow_nan=False) + "\n" for row in body)
    files["capture/evidence.jsonl"] = "".join(json.dumps(row, allow_nan=False) + "\n" for row in evidence)
    files["lateral_control_setpoint_source.jsonl"] = "".join(
        json.dumps({"frame": row["carla_frame"], "time_s": row["time_s"],
                    "lateral_control_setpoint_m": setpoint_m}) + "\n"
        for row in [json.loads(line) for line in files["video_frames.jsonl"].splitlines()])
    capture_manifest = json.loads(files["capture/manifest.json"])
    capture_manifest["sources"]["trace.jsonl"] = sha256(files["trace.jsonl"].encode()).hexdigest()
    files["capture/manifest.json"] = json.dumps(capture_manifest, indent=2) + "\n"
    return result


def build(output: Path) -> list[dict]:
    """Write the 6 x 4 source-derived variants to ignored local staging."""
    output = output.resolve()
    if ROOT / ".runtime-work" not in output.parents or output.exists():
        raise ValueError("Choose a fresh directory under ignored .runtime-work")
    proposal = json.loads((HERE / "proposals/cases.json").read_text())
    manifest = json.loads((HERE / "provisional-manifest.json").read_text())
    specs = {spec["sweep_id"]: spec for spec in proposal["sweep_specs"]}
    if set(specs) != set(SOURCE_CASES):
        raise ValueError("Heavy-lane sweep inventory changed")
    planned = []
    for sweep_id, suffix in SOURCE_CASES.items():
        spec = specs[sweep_id]
        if len(spec["axes"]) != 1 or spec["axes"][0]["variable"] != "lateral_control_setpoint_m":
            raise ValueError("Unsupported heavy-lane sweep axis")
        base_case = HERE.name + "__" + suffix
        matches = [case for case in manifest["cases"] if case["case_id"] == base_case]
        if len(matches) != 1:
            raise ValueError("Selected base case is missing")
        base = matches[0]
        candidates = [("primary", base)] + [(candidate["id"], candidate) for candidate in base["candidates"]]
        if [item[0] for item in candidates] != ["primary", "fallback1", "fallback2", "fallback3"]:
            raise ValueError("Expected selected primary and three distinct fallback plans")
        for rank, point in enumerate(grid(spec)):
            case_id = f"{sweep_id}-{rank:04d}"
            target = point["lateral_control_setpoint_m"]
            for candidate_id, candidate in candidates:
                source_path = HERE / candidate["construction"]
                if sha256(source_path.read_bytes()).hexdigest() != candidate["construction_sha256"]:
                    raise ValueError("Selected construction source changed")
                variant = _variant(json.loads(source_path.read_text()), base_case, case_id, target)
                path = Path(sweep_id) / case_id / f"{candidate_id}-construction.json"
                planned.append({"case_id": case_id, "source_case_id": base_case,
                                "candidate_id": candidate_id, "setpoint_m": target,
                                "path": str(path), "source_sha256": candidate["construction_sha256"],
                                "construction": variant})
    output.mkdir(parents=True)
    index = []
    for item in planned:
        destination = output / item["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(item["construction"], indent=2) + "\n")
        index.append({key: value for key, value in item.items() if key != "construction"}
                     | {"sha256": sha256(destination.read_bytes()).hexdigest()})
    (output / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    cases = []
    for case_id in dict.fromkeys(item["case_id"] for item in index):
        selected = [item for item in index if item["case_id"] == case_id]
        primary = selected[0]
        if primary["candidate_id"] != "primary":
            raise ValueError("Sweep primary selection order differs")
        source = next(case for case in manifest["cases"]
                      if case["case_id"] == primary["source_case_id"])
        cases.append({"case_id": case_id, "construction": primary["path"],
                      "construction_sha256": primary["sha256"],
                      "candidate_risk": deepcopy(source["candidate_risk"]),
                      "candidates": [{"id": item["candidate_id"],
                                      "construction": item["path"],
                                      "construction_sha256": item["sha256"],
                                      "trigger": deepcopy(next(candidate["trigger"]
                                          for candidate in source["candidates"]
                                          if candidate["id"] == item["candidate_id"])),
                                      "changed_knobs": deepcopy(next(candidate["changed_knobs"]
                                          for candidate in source["candidates"]
                                          if candidate["id"] == item["candidate_id"]))}
                                     for item in selected[1:]]})
    (output / "offline-manifest.json").write_text(json.dumps({
        "format": "worker-provisional-manifest", "assignment_id": HERE.name,
        "cases": cases,
    }, indent=2) + "\n")
    for case in cases:
        validate_candidates(output, case, "LVMC-11-18-030-B", "C305951",
                            required=False, require_alternate=True, candidate_count=4)
    return index


def stage_diagnostics(output: Path) -> list[dict]:
    """Materialize six source-joined synthetic capture diagnostics in staging."""
    output = output.resolve()
    if ROOT / ".runtime-work" not in output.parents or output.exists():
        raise ValueError("Choose a fresh directory under ignored .runtime-work")
    output.mkdir(parents=True)
    rows = []
    for sweep_id, branch in ((HERE.name + "__heavy_passing_plan", "passing"),
                             (HERE.name + "__heavy_turn_plan", "turn")):
        source_path = HERE / (branch + "-diagnostic.json")
        source = json.loads(source_path.read_text())
        for rank, setpoint in enumerate((0.0, 2.2, 1.1)):
            case_id = f"{sweep_id}-{rank:04d}"
            diagnostic = diagnostic_at_setpoint(source, setpoint)
            path = output / (case_id + "-diagnostic.json")
            # A returned diagnostic specification must stay below the 2 MiB
            # text-file limit; its graph observations dominate pretty JSON.
            encoded = json.dumps(diagnostic, separators=(",", ":"), allow_nan=False) + "\n"
            if len(encoded.encode()) > 2 * 1024 * 1024:
                raise ValueError("Generated diagnostic exceeds returned text-file limit")
            path.write_text(encoded)
            fixture = output / (case_id + "-fixture")
            generate_fixture(diagnostic, fixture)
            rows.append({"case_id": case_id, "branch": branch,
                         "setpoint_m": setpoint, "source_sha256": sha256(source_path.read_bytes()).hexdigest(),
                         "diagnostic": path.name, "diagnostic_sha256": sha256(path.read_bytes()).hexdigest(),
                         "trace_sha256": sha256((fixture / "trace.jsonl").read_bytes()).hexdigest(),
                         "body_sha256": sha256((fixture / "heavy_lane_sources.jsonl").read_bytes()).hexdigest(),
                         "evidence_sha256": sha256((fixture / "capture/evidence.jsonl").read_bytes()).hexdigest()})
    (output / "index.json").write_text(json.dumps(rows, indent=2) + "\n")
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--diagnostics-output", type=Path)
    args = parser.parse_args()
    if not args.output and not args.diagnostics_output:
        parser.error("Supply construction or diagnostic staging output")
    if args.output:
        rows = build(args.output)
        print(json.dumps({"construction_variants": len(rows),
                          "exact_cases": len({row["case_id"] for row in rows}),
                          "output": str(args.output)}, indent=2))
    if args.diagnostics_output:
        rows = stage_diagnostics(args.diagnostics_output)
        print(json.dumps({"diagnostic_cases": len(rows),
                          "output": str(args.diagnostics_output)}, indent=2))
