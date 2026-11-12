"""Build a source-hashed synthetic fixture and case plan for the 100-foot rail draft."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
from copy import deepcopy
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD_SUFFIX, SUFFIX = "rail_contrast", "rail_at"
CASE_ID = HERE.name + "__" + SUFFIX
NAMES = ("native_samples.jsonl", "road_geometry.json", "statutory_context.json",
         "context.json", "video_frames.jsonl", "body_history.jsonl", "trace.jsonl",
         "capture/evidence.jsonl", "capture/manifest.json",
         "capture/native/frames.jsonl", "capture/recorder_info.txt")
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def read(path: Path):
    return json.loads(path.read_text())


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_file(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def rows(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


manifest_path = HERE / "draft-rail-at-execution-manifest.json"
manifest = read(manifest_path)
entry = manifest["cases"][0]
assert entry["case_id"] == CASE_ID
construction = read(HERE / entry["construction"])
source_files = {f["path"]: f["content"] for f in construction["files"]}
with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work", prefix="c110454-rail-at-recipe-") as temporary:
    stage = Path(temporary)
    modules = stage / "modules"
    modules.mkdir()
    for name in ("geometry_base.py", "geometry_statutory.py"):
        (modules / name).write_text(source_files[name])
    sys.path.insert(0, str(modules))
    load_file(modules / "geometry_base.py", "geometry_base")
    geometry = load_file(modules / "geometry_statutory.py", "geometry_statutory")
    geom = geometry.check()["case_results"][SUFFIX]
    assert geom["nearest_full_body_front_distance_m"] == 30.48
    route = geometry.route(SUFFIX)
    target = next(i for i, point in enumerate(route) if point[0] == -53.08)
    indices = [round(i * (len(route) - 1) / 399) for i in range(400)]
    nearest = min(range(400), key=lambda i: abs(indices[i] - target))
    indices[nearest] = target
    assert all(a < b for a, b in zip(indices, indices[1:]))
    diagnostic_route = [route[i] for i in indices]
    assert diagnostic_route[nearest][0] == -53.08 and diagnostic_route[nearest][1] - 1.1 > 0
    fixture_root = stage / "source"
    candidate = fixture_root / "draft-statutory-candidates" / SUFFIX / "primary" / "construction.json"
    candidate.parent.mkdir(parents=True)
    candidate.write_text(json.dumps(construction) + "\n")
    route_path = fixture_root / "native/routes" / (SUFFIX + ".json")
    write(route_path, diagnostic_route)
    fixture = load_file(HERE / "saved-statutory-fixture.py", "rail_at_saved_fixture")
    fixture.FOLDER = fixture_root
    probe = load_file(HERE / "probe-core-statutory.py", "rail_at_core_probe")
    source = stage / "attempt"
    fixture.make_base(source, SUFFIX, 480)
    probe.enrich(source, SUFFIX)
    files = {name: (source / name).read_text() for name in NAMES}
    files["acquisition-provenance.json"] = json.dumps({
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n"
    samples = rows(source / "native_samples.jsonl")
    evidence = rows(source / "capture/evidence.jsonl")
    frames = rows(source / "capture/native/frames.jsonl")
    assert len(samples) == len(evidence) == len(frames) == 480
    assert all(s["speed_provenance"] == "synthetic_native_sample" for s in samples)
    graphs = []
    for sample, event, frame in zip(samples, evidence, frames):
        x, y = sample["native_center_xy_m"]
        graphs.append({"path": "capture/native/" + frame["base"],
                       "attributes": {"frame": frame["frame"], "simulation_time_s": frame["simulation_time"],
                                      "synthetic_diagnostic": True},
                       "nodes": [{"id": "ego", "attributes": {"sem_class": "ego", "entity_id": 107,
                                                             "vertex": [x, y, .5], "forward": [1, 0, 0],
                                                             "threedbbox": event["ego"]["body_vertices_m"]}}],
                       "edges": []})
    videos = [{"path": name + ".mkv", "frames": 480, "width": width, "height": height,
               "fps": 20, "color": "black"} for name, width, height in CAMERAS]
    spec_path = HERE / "update034-rail-at-diagnostic.json"
    spec_path.write_text(json.dumps({"files": files, "graphs": graphs, "videos": videos},
                                    separators=(",", ":"), allow_nan=False) + "\n")
    assert spec_path.stat().st_size < 2 * 1024 * 1024
    sys.path.pop(0)

relative = spec_path.relative_to(ROOT).as_posix()
recipe = {"format": "worker-fixture-recipe",
          "sources": [{"path": "diagnostic-input.json", "source": relative, "sha256": sha(spec_path)}],
          "generator": {"source": relative, "sha256": sha(spec_path)}}
recipe_path = HERE / "update034-rail-at-recipe.json"
write(recipe_path, recipe)

old_contract = read(HERE / "draft-statutory-contracts" / OLD_SUFFIX / "measurement-contract.json")
old_contract["case_id"] = CASE_ID
contract_path = HERE / "draft-rail-at-contracts/measurement-contract.json"
write(contract_path, old_contract)
entry["fixture_recipe"] = recipe_path.relative_to(ROOT).as_posix()
entry["measurement_contract"] = contract_path.relative_to(HERE).as_posix()
entry["preparation_status"] = "draft_fixture_ready_not_selected"
write(manifest_path, manifest)

plan_path = HERE / "case-plan.json"
plan = read(plan_path)
if not any(c["case_id"] == CASE_ID for c in plan["cases"]):
    source_case = next(c for c in plan["cases"] if c["case_id"].endswith("__rail_contrast"))
    new_case = deepcopy(source_case)
    new_case.update(case_id=CASE_ID, planning_status="draft_cpu_compatibility_pending",
                    requested_setting="authored at 100 ft; original Native distance unobserved",
                    case_description="Exact statutory 100-foot railroad approach boundary draft")
    plan["cases"].append(new_case)
for disposition in plan["requirement_dispositions"][:2]:
    if CASE_ID not in disposition["case_ids"]:
        disposition["case_ids"].append(CASE_ID)
if not any(c["comparison_id"].endswith("__comparison_rail_at") for c in plan["comparisons"]):
    comparison = deepcopy(next(c for c in plan["comparisons"] if c["comparison_id"].endswith("__comparison_rail")))
    comparison["comparison_id"] = HERE.name + "__comparison_rail_at"
    comparison["case_ids"] = [HERE.name + "__rail_reference", CASE_ID]
    comparison["status"] = "draft_cpu_compatibility_pending"
    plan["comparisons"].append(comparison)
write(plan_path, plan)

cases_path = HERE / "proposals/cases.json"
cases = read(cases_path)
if not any(c["case_id"] == CASE_ID for c in cases["cases"]):
    old_case = next(c for c in cases["cases"] if c["case_id"].endswith("__rail_contrast"))
    new_case = deepcopy(old_case)
    new_case["case_id"] = CASE_ID
    new_case["recording_description"] = construction["recording_description"]
    cases["cases"].append(new_case)
write(cases_path, cases)
print(json.dumps({"case_id": CASE_ID, "diagnostic_sha256": sha(spec_path),
                  "recipe_sha256": sha(recipe_path), "manifest_sha256": sha(manifest_path),
                  "frames": 480, "authored_boundary_m": geom["nearest_full_body_front_distance_m"]}, indent=2))
