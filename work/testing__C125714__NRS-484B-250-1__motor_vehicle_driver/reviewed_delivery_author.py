"""Author seven delivery construction candidates from retained reviewed sources.

This does not create source findings or delivery proof receipts. Every input
scene, packet, and source byte must be supplied by a reviewer first.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from case_builder import config, recording_description
from diagnostic_construction_author import spawn_clearance_candidate
from preflight_reviewed_packet import preflight
from runner import check_scene, resolve_reviewed_source


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SUFFIXES = ("precedence", "advance", "other_later", "opposite_straight",
            "opposite_intends_left", "opposite_makes_left", "wide_same_crossing")
CODE = ("runner.py", "case_builder.py", "crossing_control.py", "crossing_audit.py",
        "native_capture.py", "native_driver.py", "analysis.py", "delivery_audit.py",
        "precedence_response_audit.py", "tests/test_reviewed_delivery_bundle.py")
SOURCE_KEYS = ("public_access_source", "device_inventory_source", "driver_scope_source")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utf8_exact(path):
    """Decode reviewed bytes without universal-newline conversion."""
    return Path(path).read_bytes().decode("utf-8")


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def reviewed_fixture(folder, suffix, packet_text, map_text):
    """Bind a synthetic CPU diagnostic to the reviewed construction sources.

    The body positions and black videos remain synthetic. The returned recipe
    only tests software compatibility and must never be treated as a capture.
    """
    original = ROOT if suffix == "precedence" else ROOT / "cases" / suffix
    spec = deepcopy(json.loads((original / "diagnostic.json").read_text()))
    packet = json.loads(packet_text)
    context = deepcopy(packet)
    context.update(diagnostic_only=True, ego_actor_id=11, other_actor_id=22,
                   reviewed_context_sha256=hashlib.sha256(packet_text.encode("utf-8")).hexdigest())
    files = spec["files"]
    files["intersection-context.json"] = json.dumps(context, separators=(",", ":"),
                                                       ensure_ascii=False) + "\n"
    files["reviewed-context.json"] = packet_text
    files["acquisition.json"] = json.dumps({
        name: {"kind": "original_native", "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()}
        for name, content in files.items()
        if name in ("intersection-context.json", "ego-body-history.jsonl",
                    "other-body-history.jsonl", "reviewed-context.json")
    }, separators=(",", ":")) + "\n"
    capture = json.loads(files["capture/manifest.json"])
    capture["sources"]["road.xodr"] = hashlib.sha256(map_text.encode("utf-8")).hexdigest()
    files["capture/manifest.json"] = json.dumps(capture, separators=(",", ":")) + "\n"
    map_path = folder / "reviewed-map.xodr"
    map_path.write_text(map_text, encoding="utf-8")
    spec_path = folder / "reviewed-diagnostic.json"
    write_json(spec_path, spec)
    recipe_path = folder / "reviewed-diagnostic-recipe.json"
    write_json(recipe_path, {
        "format": "worker-fixture-recipe",
        "sources": [{"path": "road.xodr", "source": str(map_path.relative_to(REPO)),
                     "sha256": digest(map_path)}],
        "generator": {"source": str(spec_path.relative_to(REPO)), "sha256": digest(spec_path)},
    })
    return recipe_path


def safe_relative(base, relative):
    if (not isinstance(relative, str) or not relative or Path(relative).is_absolute()
            or ".." in Path(relative).parts):
        raise ValueError("source path must be packet relative")
    source = base / relative
    if source.is_symlink():
        raise ValueError("review source cannot be a symlink")
    result = source.resolve()
    if not result.is_relative_to(base.resolve()) or not result.is_file():
        raise ValueError("review source missing or escapes packet directory")
    return result


def source_files(scene_path):
    scene_path = Path(scene_path)
    scene = check_scene(json.loads(scene_path.read_text()))
    packet_source = Path(scene["reviewed_context_source"])
    if packet_source.is_absolute() or ".." in packet_source.parts:
        raise ValueError("reviewed packet must be case relative")
    if (scene_path.parent / packet_source).is_symlink():
        raise ValueError("reviewed packet cannot be a symlink")
    packet_path = resolve_reviewed_source(scene, scene_path)
    packet = json.loads(packet_path.read_text())
    if scene.get("diagnostic_only") is not False or packet.get("diagnostic_only") is not False:
        raise ValueError("reviewed delivery author rejects diagnostic sources")
    if not packet_path.is_relative_to(scene_path.parent.resolve()):
        raise ValueError("reviewed packet must be in the case source directory")
    files = {"scene.json": utf8_exact(scene_path),
             "config.json": json.dumps(config(scene), indent=2, ensure_ascii=False) + "\n"}
    packet_rel = packet_path.relative_to(scene_path.parent.resolve()).as_posix()
    if packet_rel in files or packet_rel in CODE or packet_rel == "reviewed-map.xodr":
        raise ValueError("reviewed packet path collides with construction file")
    files[packet_rel] = utf8_exact(packet_path)
    for key in SOURCE_KEYS:
        descriptor = packet["law_context"].get(key)
        if not isinstance(descriptor, dict):
            raise ValueError("reviewed source descriptor missing: " + key)
        path = safe_relative(packet_path.parent, descriptor.get("source_path"))
        rel = path.relative_to(scene_path.parent.resolve()).as_posix()
        if digest(path) != descriptor.get("source_sha256"):
            raise ValueError("reviewed source hash changed: " + key)
        if rel in files or rel in CODE or rel == "reviewed-map.xodr":
            raise ValueError("reviewed source path collides with construction file: " + rel)
        try:
            files[rel] = utf8_exact(path)
        except UnicodeDecodeError as error:
            raise ValueError("inline construction source is not UTF-8: " + key) from error
    for name in CODE:
        files[name] = (ROOT / name).read_text()
    return scene, files


def check_comparison_isolation(by_name, packets=None):
    common = ("crossing", "ego_highway", "other_highway", "ego_route_xy_m",
              "other_route_xy_m", "capture_rate_hz", "duration_s",
              "ego_approach_road_id", "other_approach_road_id",
              "approach_relation", "left_turn_intent", "left_turn_realized",
              "other_entered_first", "ego_response_request")
    for left, right, changed in (
            ("precedence", "advance", ("ego_response_request",)),
            ("advance", "other_later", ("other_entered_first",)),
            ("opposite_straight", "opposite_intends_left", ("left_turn_intent",)),
            ("opposite_intends_left", "opposite_makes_left",
             ("left_turn_realized", "other_route_xy_m"))):
        a, b = by_name[left], by_name[right]
        if any(a.get(key) != b.get(key) for key in common if key not in changed):
            raise ValueError("frozen comparison changed a fixed scene field: " + left + "/" + right)
        if any(a.get(key) == b.get(key) for key in changed):
            raise ValueError("frozen comparison lacks declared scene difference: " + left + "/" + right)
    a, b = by_name["precedence"], by_name["wide_same_crossing"]
    wide_fixed = ("ego_highway", "other_highway", "other_route_xy_m", "capture_rate_hz",
                  "duration_s", "other_approach_road_id", "approach_relation",
                  "left_turn_intent", "left_turn_realized", "other_entered_first",
                  "ego_response_request")
    if any(a.get(key) != b.get(key) for key in wide_fixed):
        raise ValueError("separate-roadway comparison changed a fixed scene field")
    for key in ("crossing_id", "roadway_id"):
        if a["crossing"][key] == b["crossing"][key]:
            raise ValueError("separate-roadway comparison lacks distinct " + key)
    if a["crossing"]["map_source_sha256"] != b["crossing"]["map_source_sha256"]:
        raise ValueError("separate-roadway comparison changed the map")
    left_dx = a["ego_route_xy_m"][-1][0] - a["ego_route_xy_m"][0][0]
    right_dx = b["ego_route_xy_m"][-1][0] - b["ego_route_xy_m"][0][0]
    if left_dx * right_dx >= 0:
        raise ValueError("separate-roadway comparison lacks opposite ego approach directions")
    if packets is not None:
        source_fields = ("map_source", "public_access", "human_driver", "devices",
                         "ego_highway", "other_highway", "approach_relation",
                         "public_access_source", "device_inventory_source",
                         "driver_scope_source")
        for left, right, changed in (
                ("precedence", "advance", ()),
                ("advance", "other_later", ()),
                ("opposite_straight", "opposite_intends_left", ("left_turn_intent",)),
                ("opposite_intends_left", "opposite_makes_left", ("left_turn_realized",)),
                ("precedence", "wide_same_crossing", ())):
            a = packets[left]["law_context"]
            b = packets[right]["law_context"]
            for key in (*source_fields, "left_turn_intent", "left_turn_realized"):
                if key in changed:
                    continue
                a_value, b_value = a.get(key), b.get(key)
                if key in SOURCE_KEYS:
                    a_value = a_value.get("source_sha256") if isinstance(a_value, dict) else None
                    b_value = b_value.get("source_sha256") if isinstance(b_value, dict) else None
                if a_value != b_value:
                    raise ValueError("fixed reviewed law context changed: " + left + "/" + right + "/" + key)


def author(source_root, map_path, output_root, proof_root, *, scratch_output=False):
    source_root, map_path, output_root, proof_root = map(
        Path, (source_root, map_path, output_root, proof_root))
    if output_root.exists() or proof_root.exists():
        raise ValueError("use fresh candidate and preflight output directories")
    allowed_output = REPO / ".runtime-work" if scratch_output else ROOT
    if not output_root.resolve().is_relative_to(allowed_output):
        raise ValueError("delivery candidate output must stay in this assignment")
    if not proof_root.resolve().is_relative_to(REPO / ".runtime-work"):
        raise ValueError("preflight output must stay under .runtime-work")
    if not map_path.is_file():
        raise ValueError("reviewed OpenDRIVE file is missing")
    try:
        map_text = utf8_exact(map_path)
    except UnicodeDecodeError as error:
        raise ValueError("reviewed OpenDRIVE must be UTF-8 for inline construction") from error
    staged = []
    for suffix in SUFFIXES:
        scene_path = source_root / suffix / "scene.json"
        scene, files = source_files(scene_path)
        expected = ROOT.name + "__" + suffix
        if scene["case_id"] != expected:
            raise ValueError("frozen exact case ID differs: " + suffix)
        if scene["crossing"]["map_source_sha256"] != digest(map_path):
            raise ValueError("reviewed map differs from scene: " + suffix)
        staged.append((suffix, scene_path, scene, files))
    check_comparison_isolation(
        {suffix: scene for suffix, _, scene, _ in staged},
        {suffix: json.loads(files[Path(scene["reviewed_context_source"]).as_posix()])
         for suffix, _, scene, files in staged})
    for suffix, scene_path, _, _ in staged:
        preflight(scene_path, map_path, proof_root / suffix)
    output_root.mkdir(parents=True)
    (output_root / "proposals").mkdir()
    for source, destination in ((ROOT / "case-plan.json", output_root / "case-plan.json"),
                                (ROOT / "proposals/cases.json", output_root / "proposals/cases.json")):
        destination.write_bytes(source.read_bytes())
    manifest = {"format": "worker-reviewed-delivery-candidates", "assignment_id": ROOT.name,
                "reviewed_map_sha256": digest(map_path),
                "runtime_manifest_sha256": digest(REPO / "runtime/SOURCE-MANIFEST.json"),
                "cases": []}
    for suffix, _, scene, files in staged:
        folder = output_root / suffix
        folder.mkdir()
        files = {**files, "reviewed-map.xodr": map_text}
        construction = {"law_id": "NRS-484B-250-1", "cell_id": "C125714",
                        "actor": "motor_vehicle_driver", "case_id": scene["case_id"],
                        "diagnostic_only": False, "entrypoint": "runner.py",
                        "files": [{"path": key, "content": value} for key, value in sorted(files.items())],
                        "recording_description": recording_description(),
                        "mechanisms": ["reviewed original context and map binding",
                                       "other actor route and ego response controller",
                                       "sealed original body and four-camera capture"],
                        "measurement_plan": {"entry_and_clearance": "original body polygons and frame joins"},
                        "static_checks": ["reviewed source preflight", "exact config and route binding"],
                        "termination_rules": ["Native restoration and capture seal before saved processing"]}
        path = folder / "construction.json"
        write_json(path, construction)
        if path.stat().st_size > 2 * 1024 * 1024:
            path.unlink()
            raise ValueError("delivery construction exceeds the 2 MiB return limit")
        fallback = spawn_clearance_candidate(construction)
        fallback_scene = json.loads(next(item["content"] for item in fallback["files"]
                                         if item["path"] == "scene.json"))
        next(item for item in fallback["files"] if item["path"] == "config.json")["content"] = (
            json.dumps(config(fallback_scene), indent=2, ensure_ascii=False) + "\n")
        fallback_path = folder / "fallback1-construction.json"
        write_json(fallback_path, fallback)
        if fallback_path.stat().st_size > 2 * 1024 * 1024:
            fallback_path.unlink()
            raise ValueError("delivery fallback exceeds the 2 MiB return limit")
        diagnostic_folder = ROOT if suffix == "precedence" else ROOT / "cases" / suffix
        contract_path = folder / "measurement-contract.json"
        contract_path.write_bytes((diagnostic_folder / "measurement-contract.json").read_bytes())
        packet_rel = Path(scene["reviewed_context_source"]).as_posix()
        recipe_path = reviewed_fixture(folder, suffix, files[packet_rel], map_text)
        measurement = json.loads(contract_path.read_text())
        acquisition = {
            requirement["requirement"]: {
                "entrypoint": "native_capture.py",
                "method": "original Native frame acquisition, retained reviewed crossing context and saved body-history analysis",
                "evidence": ", ".join(requirement["inputs"]),
            }
            for requirement in measurement["requirements"]
        }
        saved_command = (
            f"PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved "
            f"--manifest work/{ROOT.name}/execution-manifest.json "
            f"--case {scene['case_id']} --attempt \"$ATTEMPT\" "
            "--output \"$SAVED_OUTPUT\" --library \"$LIBRARY\" "
            "--validator \"$VALIDATOR\""
        )
        manifest["cases"].append({"case_id": scene["case_id"],
                                  "kind": "delivery",
                                  "construction": str(path.relative_to(output_root)),
                                  "construction_sha256": digest(path),
                                  "measurement_contract": str(contract_path.relative_to(output_root)),
                                  "measurement_procedure": {"entrypoint": "analysis.py"},
                                  "fixture_recipe": str(recipe_path.relative_to(REPO)),
                                  "acquisition": acquisition,
                                  "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                                     "host_env_var": "CARLA_HOST",
                                                     "port_env_var": "CARLA_PORT"},
                                  "post_capture": {"recorded_only": True,
                                                   "command": saved_command,
                                                   "feedback_command": saved_command,
                                                   "proof_scope": "reviewed-source delivery; passing saved-only test receipt still required"},
                                  "candidate_risk": {"status": "physical", "reason":
                                      "An initial actor spawn can be occupied before capture."},
                                  "candidates": [{"id": "fallback1",
                                      "construction": str(fallback_path.relative_to(output_root)),
                                      "construction_sha256": digest(fallback_path),
                                      "trigger": {"source": "Native spawn_vehicles attempt log",
                                                  "metric": "initial ego or other spawn result",
                                                  "failure_condition": "either initial spawn_actor returns no actor"},
                                      "changed_knobs": ["both initial spawn points 2 m upstream on the same approaches"]}],
                                  "source_preflight": str((proof_root / suffix / "preflight.json").relative_to(REPO))})
    write_json(output_root / "candidate-index.json", manifest)
    return manifest


def compatibility_manifest(candidate_root, destination):
    """Bind staged paths to the assignment root for pinned compatibility CLI."""
    candidate_root, destination = Path(candidate_root).resolve(), Path(destination).resolve()
    if not candidate_root.is_relative_to(ROOT) or destination.parent != ROOT:
        raise ValueError("compatibility manifest must resolve from the assignment root")
    if destination.exists():
        raise ValueError("retain the previous compatibility manifest")
    result = deepcopy(json.loads((candidate_root / "candidate-index.json").read_text()))
    prefix = candidate_root.relative_to(ROOT)
    for entry in result["cases"]:
        for key in ("construction", "measurement_contract"):
            entry[key] = str(prefix / entry[key])
        for candidate in entry["candidates"]:
            candidate["construction"] = str(prefix / candidate["construction"])
    write_json(destination, result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--map", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--preflight-root", required=True)
    parser.add_argument("--compatibility-manifest")
    args = parser.parse_args()
    result = author(args.source_root, args.map, args.output_root, args.preflight_root)
    if args.compatibility_manifest:
        compatibility_manifest(args.output_root, args.compatibility_manifest)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
