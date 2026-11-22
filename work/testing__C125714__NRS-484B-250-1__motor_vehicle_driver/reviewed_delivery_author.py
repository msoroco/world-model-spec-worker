"""Author seven delivery construction candidates from retained reviewed sources.

This does not create source findings or delivery proof receipts. Every input
scene, packet, and source byte must be supplied by a reviewer first.
"""
from __future__ import annotations

import argparse
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


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def safe_relative(base, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("source path must be packet relative")
    result = (base / relative).resolve()
    if not result.is_relative_to(base.resolve()) or not result.is_file():
        raise ValueError("review source missing or escapes packet directory")
    return result


def source_files(scene_path):
    scene_path = Path(scene_path)
    scene = check_scene(json.loads(scene_path.read_text()))
    packet_path = resolve_reviewed_source(scene, scene_path)
    packet = json.loads(packet_path.read_text())
    if scene.get("diagnostic_only") is not False or packet.get("diagnostic_only") is not False:
        raise ValueError("reviewed delivery author rejects diagnostic sources")
    if not packet_path.is_relative_to(scene_path.parent.resolve()):
        raise ValueError("reviewed packet must be in the case source directory")
    files = {"scene.json": scene_path.read_text(),
             "config.json": json.dumps(config(scene), indent=2, ensure_ascii=False) + "\n"}
    packet_rel = packet_path.relative_to(scene_path.parent.resolve()).as_posix()
    files[packet_rel] = packet_path.read_text()
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
            files[rel] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("inline construction source is not UTF-8: " + key) from error
    for name in CODE:
        files[name] = (ROOT / name).read_text()
    return scene, files


def author(source_root, map_path, output_root, proof_root):
    source_root, map_path, output_root, proof_root = map(
        Path, (source_root, map_path, output_root, proof_root))
    if output_root.exists() or proof_root.exists():
        raise ValueError("use fresh candidate and preflight output directories")
    if not output_root.resolve().is_relative_to(ROOT):
        raise ValueError("delivery candidate output must stay in this assignment")
    if not proof_root.resolve().is_relative_to(REPO / ".runtime-work"):
        raise ValueError("preflight output must stay under .runtime-work")
    if not map_path.is_file():
        raise ValueError("reviewed OpenDRIVE file is missing")
    try:
        map_text = map_path.read_text(encoding="utf-8")
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
    # Validate the fixed condition of the two frozen crossing comparisons.
    by_name = {suffix: scene for suffix, _, scene, _ in staged}
    for left, right, variable in (("precedence", "advance", "ego_response_request"),
                                  ("advance", "other_later", "other_entered_first")):
        a, b = by_name[left], by_name[right]
        shared = ("crossing", "ego_highway", "other_highway", "ego_route_xy_m",
                  "other_route_xy_m", "capture_rate_hz", "duration_s")
        if any(a.get(key) != b.get(key) for key in shared) or a.get(variable) == b.get(variable):
            raise ValueError("frozen crossing comparison is not isolated: " + left + "/" + right)
    for suffix, scene_path, _, _ in staged:
        preflight(scene_path, map_path, proof_root / suffix)
    output_root.mkdir(parents=True)
    manifest = {"format": "worker-reviewed-delivery-candidates", "assignment_id": ROOT.name,
                "reviewed_map_sha256": digest(map_path), "cases": []}
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
        manifest["cases"].append({"case_id": scene["case_id"],
                                  "construction": str(path.relative_to(output_root)),
                                  "construction_sha256": digest(path),
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--map", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--preflight-root", required=True)
    args = parser.parse_args()
    print(json.dumps(author(args.source_root, args.map, args.output_root,
                            args.preflight_root), indent=2))


if __name__ == "__main__":
    main()
