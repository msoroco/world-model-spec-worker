"""Build source-shaped synthetic diagnostics for physical-obstruction drafts."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "native"))
from activity_controller import command

REPO = ROOT.parents[1]
BASE = ROOT / "selected-source/condition_a"
CHANGED = {"native_samples.jsonl", "trace.jsonl", "capture/evidence.jsonl",
           "capture/manifest.json",
           "exception-context.json", "obstruction-inventory.json"}
FILES = ("acquisition-provenance.json", "capture/evidence.jsonl", "capture/manifest.json",
         "capture/native/frames.jsonl", "capture/recorder_info.txt", "trace.jsonl",
         "video_frames.jsonl", "road.xodr", "obstruction-inventory.json",
         "native_samples.jsonl", "camera-frames.jsonl", "exception-context.json")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(value, allow_nan=False) + "\n" for value in values))


def build(name):
    plan = json.loads((ROOT / "statutory-branch-draft.json").read_text())
    entry = next((item for item in plan["cases"] if item["case_id"].endswith("selected_statutory_" + name)), None)
    if entry is None or entry["requests"]["obstruction_kind_request"] != "physical_obstruction":
        raise ValueError("Unknown physical-obstruction draft")
    request = entry["requests"]
    case_id = entry["case_id"]
    target = ROOT / "selected-source" / ("statutory-" + name)
    target.mkdir(parents=True, exist_ok=True)
    flags = {key: request["exception_request"] == key for key in
             ("traffic_conflict", "law_direction", "police_direction", "traffic_device")}
    reviewed = {key + "_reviewed": True for key in flags}
    write(target / "exception-context.json", {
        "case_id": case_id, "source_kind": "synthetic_cpu",
        "activity_request": request["activity_request"],
        "placement_request": request["placement_request"],
        "obstruction_kind_request": request["obstruction_kind_request"],
        "exception_request": request["exception_request"],
        "exceptions": flags, "exception_source": reviewed,
        "legal_verdict_claimed": False})
    inventory = json.loads((BASE / "obstruction-inventory.json").read_text())
    inventory["case_id"] = case_id
    write(target / "obstruction-inventory.json", inventory)
    sample = rows(BASE / "native_samples.jsonl")
    trace = rows(BASE / "trace.jsonl")
    evidence = rows(BASE / "capture/evidence.jsonl")
    center_x, center_y = ((7.5, 2.2) if request["placement_request"] == "alongside"
                          else (2.5, -2.2))
    for index, (s, core, sensor) in enumerate(zip(sample, trace, evidence)):
        phase = command(request["activity_request"], index)
        if phase["phase"] == "approach":
            speed = .12
            x = center_x - .36 + index * speed / 20
        elif phase["phase"] == "departure":
            start = 140 if request["activity_request"] == "stop" else 440
            speed = .18
            x = center_x + (index - start) * speed / 20
        else:
            speed, x = 0.0, center_x
        body = [x - 2.4, center_y - .9, x + 2.4, center_y + .9]
        s.update(ego_body_xy_m=body, ego_speed_m_s=speed,
                 activity_request=request["activity_request"],
                 placement_request=request["placement_request"],
                 activity_controller_phase=phase["phase"],
                 exceptions=flags, exception_source=reviewed)
        core["position"] = {"x": x, "y": center_y, "z": 1.1}
        core["position_m"] = [x, center_y, 1.1]
        core["speed_mps"] = speed
        core["speed_mph"] = speed * 2.2369362921
        core["velocity_mps"] = [speed, 0, 0]
        core["control"] = {key: phase[key] for key in ("throttle", "brake", "hand_brake")}
        ego = sensor["ego"]
        ego["position_m"] = [x, center_y, 1.1]
        ego["speed_mps"] = speed
        ego["body_vertices_m"] = [[bx, by, z] for bx in (body[0], body[2])
                                  for by in (body[1], body[3]) for z in (0, 1.5)]
    write_rows(target / "native_samples.jsonl", sample)
    write_rows(target / "trace.jsonl", trace)
    write_rows(target / "capture/evidence.jsonl", evidence)
    capture_manifest = json.loads((BASE / "capture/manifest.json").read_text())
    capture_manifest["sources"]["trace.jsonl"] = digest(target / "trace.jsonl")
    write(target / "capture/manifest.json", capture_manifest)
    recipe = {"format": "worker-fixture-recipe", "sources": []}
    for name_in_recipe in FILES:
        source = (target if name_in_recipe in CHANGED else BASE) / name_in_recipe
        recipe["sources"].append({"path": name_in_recipe,
                                  "source": str(source.relative_to(REPO)),
                                  "sha256": digest(source)})
    generator = ROOT / "selected-generator.json"
    recipe["generator"] = {"source": str(generator.relative_to(REPO)),
                           "sha256": digest(generator)}
    write(ROOT / ("selected-recipe-statutory-" + name + ".json"), recipe)
    return {"case_id": case_id, "synthetic_only": True,
            "recipe_sha256": digest(ROOT / ("selected-recipe-statutory-" + name + ".json"))}


if __name__ == "__main__":
    import sys
    print(json.dumps(build(sys.argv[1])))
