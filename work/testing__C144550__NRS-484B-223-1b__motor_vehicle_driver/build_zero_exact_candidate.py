"""Stage a separate exact zero-frame candidate for offline CPU proof.

This leaves the current selected execution manifest and its 20 proved
constructions untouched until the new candidate has independent receipts.
"""

import copy
import hashlib
import json
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = "left_signal_late_clear_gap"
NEW = "left_signal_at_departure_clear_gap"
OLD_ID = HERE.name + "__" + OLD
NEW_ID = HERE.name + "__" + NEW
CASE_DIR = HERE / "cases" / NEW


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def change(source, old, new):
    if source.count(old) != 1:
        raise ValueError("Unexpected source patch count: " + old[:60])
    return source.replace(old, new)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":")) + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Returned candidate file too large: " + str(path))


def build():
    old_construction = json.loads((HERE / "cases" / OLD / "construction.json").read_text())
    construction = copy.deepcopy(old_construction)
    construction["case_id"] = NEW_ID
    construction["mechanisms"] = list(construction["mechanisms"]) + [
        "calibrated Native lamp stage with original-frame zero-lead outcome check"]
    files = {item["path"]: item for item in construction["files"]}

    native = files["native_lane_construction.py"]["content"]
    native = change(native,
                    '    "left_signal_late_clear_gap":("left","late"),',
                    '    "left_signal_late_clear_gap":("left","late"),\n'
                    '    "left_signal_at_departure_clear_gap":("left","at"),')
    native = change(native,
                    'def indicator_command(case_id, body_left_source_lane):',
                    'def indicator_command(case_id, body_left_source_lane, signal_stage_active=False):')
    native = change(native,
                    '    if policy=="late" and not body_left_source_lane:return "off"',
                    '    if policy=="at":\n'
                    '        if type(signal_stage_active) is not bool:raise ValueError("Boolean signal stage required")\n'
                    '        return direction if signal_stage_active else "off"\n'
                    '    if policy=="late" and not body_left_source_lane:return "off"')
    native = change(native,
                    '                            target_waypoint=None):',
                    '                            target_waypoint=None, signal_stage_active=False):')
    native = change(native,
                    'indicator_command(case_id,body_left_source_lane))',
                    'indicator_command(case_id,body_left_source_lane,signal_stage_active))')
    native = change(native,
                    '                        frames=900, target_speed_mps=5.0):',
                    '                        frames=900, target_speed_mps=5.0, signal_stage_tick=None):')
    native = change(native,
                    '    rows=[];last_frame=-1;last_time=-math.inf;left_source=False',
                    '    if case_id.endswith("__left_signal_at_departure_clear_gap") and (\n'
                    '            type(signal_stage_tick) is not int or not 1<=signal_stage_tick<frames):\n'
                    '        raise ValueError("Explicit calibrated signal stage tick required")\n'
                    '    rows=[];last_frame=-1;last_time=-math.inf;left_source=False')
    native = change(native, '        for _ in range(frames):',
                    '        for tick_index in range(frames):')
    native = change(native,
                    'target_speed_mps=target_speed_mps,target_waypoint=target_waypoint)',
                    'target_speed_mps=target_speed_mps,target_waypoint=target_waypoint,\n'
                    '                signal_stage_active=(signal_stage_tick is not None and tick_index>=signal_stage_tick))')
    files["native_lane_construction.py"]["content"] = native
    files["native_lane_construction.py"]["source"] = None

    runner = files["runner.py"]["content"]
    runner = change(runner,
                    'target_speed_mps=config.get("target_speed_mps",5.0))',
                    'target_speed_mps=config.get("target_speed_mps",5.0),\n'
                    '                        signal_stage_tick=config.get("signal_stage_tick"))')
    files["runner.py"]["content"] = runner
    files["runner.py"]["source"] = None

    measure = files["lane_change_measurements.py"]["content"]
    measure = change(measure,
                     '    "left_signal_late_clear_gap":("left",False,"off"),',
                     '    "left_signal_late_clear_gap":("left",False,"off"),\n'
                     '    "left_signal_at_departure_clear_gap":("left",False,"left"),')
    files["lane_change_measurements.py"]["content"] = measure
    files["lane_change_measurements.py"]["source"] = None

    config = json.loads(files["config.json"]["content"])
    config["selected_case_id"] = NEW_ID
    config["supported_case_ids"].insert(2, NEW_ID)
    config["signal_stage_tick"] = 1
    files["config.json"]["content"] = json.dumps(config, indent=2) + "\n"
    write_json(CASE_DIR / "construction.json", construction)
    fallback_knobs = (("target_initial_route_distance_m", 250),
                      ("target_speed_mps", 4.2),
                      ("overview_along_m", 75))
    fallback_paths = []
    for number, (knob, value) in enumerate(fallback_knobs, 1):
        alternative = copy.deepcopy(construction)
        option_files = {item["path"]:item for item in alternative["files"]}
        option_config = copy.deepcopy(config)
        option_config[knob] = value
        option_files["config.json"]["content"] = json.dumps(option_config, indent=2) + "\n"
        path = CASE_DIR / ("fallback" + str(number) + "-construction.json")
        write_json(path, alternative)
        fallback_paths.append(path)

    diagnostic = json.loads((HERE / "cases" / OLD / "diagnostic.json").read_text())
    matching = [graph for graph in diagnostic["graphs"]
                if graph["path"] == "capture/native/graphs/base/00000101.adapter.json"]
    if len(matching) != 1:
        raise ValueError("Departure base graph missing")
    matching[0]["attributes"]["observed_evidence"]["participants"][0]["light_attributes"]["light_LeftBlinker"] = True
    write_json(CASE_DIR / "diagnostic.json", diagnostic)

    source_dir = HERE / "diagnostic-sources"
    capture_manifest = json.loads((source_dir / "late-capture-manifest.json").read_text())
    capture_manifest["case_id"] = NEW_ID
    capture_manifest["sources"]["trace.jsonl"] = sha(source_dir / "zero-trace.jsonl")
    write_json(source_dir / "zero-capture-manifest.json", capture_manifest)

    recipe = json.loads((HERE / "cases" / OLD / "diagnostic-recipe.json").read_text())
    names = {"lane_history.jsonl":"zero-lane_history.jsonl",
             "trace.jsonl":"zero-trace.jsonl",
             "capture/evidence.jsonl":"zero-capture-evidence.jsonl",
             "capture/manifest.json":"zero-capture-manifest.json"}
    for entry in recipe["sources"]:
        if entry["path"] in names:
            entry["source"] = "work/" + HERE.name + "/diagnostic-sources/" + names[entry["path"]]
            entry["sha256"] = sha(source_dir / names[entry["path"]])
    recipe["generator"] = {"source":"work/" + HERE.name + "/cases/" + NEW + "/diagnostic.json",
                           "sha256":sha(CASE_DIR / "diagnostic.json")}
    write_json(CASE_DIR / "diagnostic-recipe.json", recipe)

    original = json.loads((HERE / "execution-manifest.json").read_text())
    selected = next(entry for entry in original["cases"] if entry["case_id"] == OLD_ID)
    entry = copy.deepcopy(selected)
    entry["case_id"] = NEW_ID
    entry["construction"] = "cases/" + NEW + "/construction.json"
    entry["construction_sha256"] = sha(CASE_DIR / "construction.json")
    entry["fixture_recipe"] = recipe["generator"]["source"].replace("diagnostic.json", "diagnostic-recipe.json")
    entry["candidates"] = [
        {"id":"fallback"+str(number),
         "construction":"cases/"+NEW+"/"+path.name,
         "construction_sha256":sha(path),
         "risk":"Native motion or camera view at the selected lane site may differ from the primary target"}
        for number,path in enumerate(fallback_paths,1)]
    for stale in ("offline", "compatibility", "negative", "post_capture", "diagnostic_saved_processing"):
        entry.pop(stale, None)
    entry["status"] = "unselected_zero_frame_cpu_candidate"
    manifest = {"format": original["format"], "assignment_id": original["assignment_id"],
                "runtime_manifest_sha256":sha(ROOT / "runtime/SOURCE-MANIFEST.json"), "cases": [entry]}
    write_json(HERE / "zero-execution-manifest.json", manifest)
    staging = ROOT / ".runtime-work" / "c144550-zero-stage"
    (staging / "cases" / NEW).mkdir(parents=True, exist_ok=True)
    (staging / "proposals").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CASE_DIR / "construction.json", staging / entry["construction"])
    for path in fallback_paths:
        shutil.copyfile(path, staging / "cases" / NEW / path.name)
    shutil.copyfile(HERE / "measurement-contract.json", staging / "measurement-contract.json")
    staged_plan = json.loads((HERE / "case-plan.json").read_text())
    staged_plan["requirement_dispositions"][0]["case_ids"].append(NEW_ID)
    write_json(staging / "case-plan.json", staged_plan)
    proposal = json.loads((HERE / "proposals/cases.json").read_text())
    semantic = copy.deepcopy(next(item for item in proposal["cases"] if item["case_id"] == OLD_ID))
    semantic["case_id"] = NEW_ID
    semantic["rationale"] = "Synthetic zero-frame appropriate signal onset at complete body departure; physical and legal judgment unresolved"
    proposal["cases"].append(semantic)
    write_json(staging / "proposals/cases.json", proposal)
    write_json(staging / "execution-manifest.json", manifest)
    return {"case_id":NEW_ID, "construction_sha256":entry["construction_sha256"],
            "recipe_sha256":sha(CASE_DIR / "diagnostic-recipe.json"),
            "compatibility_staging":str((staging / "execution-manifest.json").relative_to(ROOT))}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
