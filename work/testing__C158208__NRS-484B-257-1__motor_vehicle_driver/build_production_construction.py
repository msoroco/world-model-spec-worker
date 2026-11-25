"""Build an exact C158208 Native construction from a reviewed site packet.

This builder never invents a map or site. The caller supplies a reviewed packet
and all eight adjacent original source files. The output remains unselected
until its own offline and delivery proofs pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from build_semantic_proposals import recording_description
from native_attempt import REVIEW_SOURCES, verify_review_sources
from source_tick_capture import validate_geometry


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
KINDS = ("nearest_view_response", "nearest_view_uninterrupted")


def build(kind: str, site_path: Path, output: Path) -> dict:
    if kind not in KINDS:
        raise ValueError("unknown exact nearest-view case")
    site_path = Path(site_path)
    output = Path(output)
    if output.exists():
        raise ValueError("production construction output already exists")
    site_bytes = site_path.read_bytes()
    site = json.loads(site_bytes)
    if site.get("review_status") != "reviewed" or site.get("cell_id") != "C158208":
        raise ValueError("reviewed C158208 Native site required")
    verify_review_sources(site, site_path, diagnostic_fixture=False)
    validate_geometry(site["capture_geometry"])
    context = site.get("reviewed_context")
    required = ("yield_sign_governs_approach", "no_marked_stop_line",
                "no_near_side_crosswalk", "no_sidewalk_derived_crosswalk",
                "through_highway_confirmed", "no_officer_control",
                "no_signal_control", "viewpoint_reviewed")
    if not isinstance(context, dict) or any(context.get(key) is not True for key in required):
        raise ValueError("reviewed nearest-view and governing-control context required")
    station = site.get("ego_view_station_m")
    if isinstance(station, bool) or not isinstance(station, (int, float)) or not math.isfinite(station):
        raise ValueError("reviewed finite nearest-view station required")
    scene_source = site.get("native_scene")
    if not isinstance(scene_source, dict) or not all(key in scene_source for key in
            ("ego", "through_vehicle", "cameras")):
        raise ValueError("reviewed Native actor and camera scene required")
    source_names = [site_path.name]
    if not site_path.name or site_path.name in ("scene.json", "config.json", "runner.py"):
        raise ValueError("reviewed site filename conflicts with construction")
    for name in REVIEW_SOURCES:
        source_names.append(site["source_bindings"][name]["path"])
    if len(source_names) != len(set(source_names)):
        raise ValueError("reviewed original source filenames must be unique")
    draft = json.loads((HERE / f"construction-{kind}.json").read_text())
    case_id = ASSIGNMENT + "__" + kind
    if draft.get("case_id") != case_id or draft.get("diagnostic_only") is not True:
        raise ValueError("exact diagnostic construction changed")
    files = {item["path"]: item["content"] for item in draft["files"]}
    files["analysis.py"] = (HERE / "analysis.py").read_text(encoding="utf-8")
    files["prepare_derived_media.py"] = (HERE / "prepare_derived_media.py").read_text(encoding="utf-8")
    files["native_capture_finalize.py"] = (HERE / "native_capture_finalize.py").read_text(encoding="utf-8")
    runner = files["runner.py"]
    old = '    run_native_attempt(client, CarlaSceneAdapter(carla), world_restore,\n'
    new = ('    from native_capture_finalize import close_capture\n'
           '    release = run_native_attempt(client, CarlaSceneAdapter(carla), world_restore,\n')
    if runner.count(old) != 1:
        raise ValueError("diagnostic runner capture handoff changed")
    runner = runner.replace(old, new)
    runner = runner.replace('from scenario_pipeline.worker_exchange import world_restore',
                            'from worker_exchange import world_restore')
    old_tail = '                       reviewed_site_packet=site, attempt=Path(args.output_dir))\n'
    new_tail = (old_tail + '    close_capture(Path(args.output_dir), release)\n')
    if runner.count(old_tail) != 1:
        raise ValueError("diagnostic runner attempt handoff changed")
    files["runner.py"] = runner.replace(old_tail, new_tail)
    scene = json.loads(files["scene.json"])
    scene.update({"source_kind": "original_reviewed_site", "site_source": site_path.name,
                  "site_sha256": hashlib.sha256(site_bytes).hexdigest(),
                  "site_source_status": "reviewed_original_source_embedded",
                  "capture_geometry": site["capture_geometry"]})
    files["scene.json"] = json.dumps(scene, indent=2, sort_keys=True) + "\n"
    for name in source_names:
        if name in files:
            raise ValueError("reviewed source filename conflicts with construction file")
        files[name] = (site_path.parent / name).read_text(encoding="utf-8")
    draft["diagnostic_only"] = False
    draft["recording_description"] = recording_description()
    draft["files"] = [{"path": path, "content": content} for path, content in files.items()]
    encoded = (json.dumps(draft, indent=2, ensure_ascii=False) + "\n").encode()
    if len(encoded) > 2 * 1024 * 1024:
        raise ValueError("production construction exceeds returned-file limit")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encoded)
    return {"case_id": case_id, "construction_sha256": hashlib.sha256(encoded).hexdigest(),
            "reviewed_site_sha256": hashlib.sha256(site_bytes).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=KINDS, required=True)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.kind, args.site, args.output), indent=2))
