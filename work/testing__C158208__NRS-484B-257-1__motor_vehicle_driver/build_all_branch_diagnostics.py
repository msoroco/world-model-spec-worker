"""Build nine explicit synthetic branch bundles for pinned CPU compatibility.

The outputs remain diagnostic-only. Genuine C158208 Native sources are neither
present nor inferred from accepted metadata or the unrelated diagnostic road.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile

from branch_site_preflight import COMMON, REFERENCE_FINDINGS, SURVEY_FOR_FINDING
from build_offline_draft import DIAGNOSTIC_GEOMETRY
from build_semantic_proposals import KINDS, case_settings, recording_description
from source_tick_capture import TickCapture, write_capture_identity


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NOTE = HERE / "fixture-source-note.json"
DONOR = "nearest_view_response"
OLD_CASE = HERE.name + "__" + DONOR
CODE_FILES = ("analysis.py", "prepare_derived_media.py", "nearest_view_measurement.py",
              "statutory_branch_measurement.py", "branch_site_preflight.py",
              "build_semantic_proposals.py", "through_traffic_control.py",
              "yield_control.py", "source_tick_capture.py", "camera_sources.py",
              "native_attempt.py", "carla_scene_adapter.py", "delivery_audit.py",
              "native_capture_finalize.py", "physical_completion.py", "saved_finalizer.py")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def site_for(kind: str, map_bytes: bytes) -> dict:
    reference = next((name for name in REFERENCE_FINDINGS if kind.startswith(name)),
                     "nearest_view")
    findings = COMMON + REFERENCE_FINDINGS[reference]
    settings = case_settings(kind)
    cited = {name: SURVEY_FOR_FINDING[name] for name in findings}
    cited["planned_through_traffic_phase"] = "through_highway_survey"
    return {"review_status": "reviewed", "source_provenance": "synthetic_fixture",
            "cell_id": "C158208", "map_opendrive_sha256": sha(map_bytes),
            "capture_geometry": DIAGNOSTIC_GEOMETRY,
            "reviewed_context": {name: True for name in findings},
            "finding_sources": cited,
            "source_bindings": {name: {"diagnostic_placeholder": True}
                                for name in set(cited.values())},
            "planned_response_mode": settings["response_mode"],
            "planned_through_traffic_phase": settings["through_traffic_phase"],
            "stopping_reference_station_m": 6.0,
            "ego_view_station_m": 6.0,
            "native_scene": {"through_vehicle": {"motion_plan": {
                "target_speed_mps": 4.0, "start_delay_s": 0.0,
                "steering_mode": "follow_reviewed_route_axis"}}}}


def _replace_case(value, case_id: str):
    if isinstance(value, str):
        return value.replace(OLD_CASE, case_id)
    if isinstance(value, list):
        return [_replace_case(item, case_id) for item in value]
    if isinstance(value, dict):
        return {key: _replace_case(item, case_id) for key, item in value.items()}
    return value


def build() -> dict:
    scratch = ROOT / ".runtime-work" / "c158208-nov25b" / "tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    os.environ["TMPDIR"] = str(scratch)
    base = json.loads((HERE / f"diagnostic-fixture-{DONOR}.json").read_text())
    donor = json.loads((HERE / f"construction-{DONOR}.json").read_text())
    note_hash = sha(NOTE.read_bytes())
    built = []
    for kind in KINDS[2:]:
        case_id = HERE.name + "__" + kind
        spec = _replace_case(copy.deepcopy(base), case_id)
        map_bytes = spec["files"]["road.xodr"].encode()
        site = site_for(kind, map_bytes)
        site_text = json.dumps(site, indent=2, sort_keys=True) + "\n"
        scene = {"case_id": case_id, "kind": kind,
                 "source_kind": "synthetic_reviewed_fixture",
                 "site_source": "diagnostic-site.json",
                 "site_sha256": sha(site_text.encode()),
                 "capture_geometry": DIAGNOSTIC_GEOMETRY,
                 "physical_acceptance": False}
        construction = copy.deepcopy(donor)
        construction["case_id"] = case_id
        construction["diagnostic_only"] = True
        construction["recording_description"] = recording_description()
        files = {row["path"]: row["content"] for row in construction["files"]}
        for name in CODE_FILES:
            files[name] = (HERE / name).read_text()
        files["runner.py"] = (HERE / "diagnostic_branch_runner.py").read_text()
        files["tests/test_bundle.py"] = (HERE / "production_bundle_test.py").read_text()
        files["diagnostic-site.json"] = site_text
        files["scene.json"] = json.dumps(scene, indent=2) + "\n"
        config = json.loads(files["config.json"])
        config["selected_case_id"] = case_id
        config["case"]["kind"] = kind
        files["config.json"] = json.dumps(config, indent=2) + "\n"
        construction["files"] = [{"path": name, "content": content}
                                 for name, content in files.items()]
        target = HERE / f"construction-{kind}.json"
        encoded = (json.dumps(construction, indent=2, ensure_ascii=False) + "\n").encode()
        if len(encoded) > 2 * 1024 * 1024:
            raise ValueError("diagnostic construction exceeds returned-file limit")
        target.write_bytes(encoded)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            temp = Path(temporary)
            attempt = temp / "attempt"
            capture = TickCapture(attempt, DIAGNOSTIC_GEOMETRY, site["reviewed_context"])
            for line in base["files"]["nearest-view-original-ticks.jsonl"].splitlines():
                capture.append(json.loads(line))
            capture.close()
            site_path = temp / "diagnostic-site.json"
            site_path.write_text(site_text)
            write_capture_identity(attempt, case_id, target, site_path, map_bytes,
                                   diagnostic_fixture=True)
            for name in ("capture-identity.json", "nearest-view-tick-seal.json",
                         "nearest-view-original-ticks.jsonl", "nearest-view-saved-packet.json"):
                spec["files"][name] = (attempt / name).read_text()
        # The construction supplies scene and site. A fixture may not shadow
        # package files during pinned compatibility materialization.
        spec["files"]["diagnostic-compatibility.json"] = json.dumps({
            "format": "c158208-generated-compatibility-v1", "case_id": case_id,
            "frame_count": 3, "source_kind": "synthetic_fixture"}, indent=2) + "\n"
        spec_target = HERE / f"diagnostic-fixture-{kind}.json"
        spec_bytes = (json.dumps(spec, indent=2, ensure_ascii=False) + "\n").encode()
        if len(spec_bytes) > 2 * 1024 * 1024:
            raise ValueError("diagnostic fixture exceeds returned-file limit")
        spec_target.write_bytes(spec_bytes)
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "fixture-source-note.json",
                               "source": f"work/{HERE.name}/fixture-source-note.json",
                               "sha256": note_hash}],
                  "generator": {"source": f"work/{HERE.name}/{spec_target.name}",
                                "sha256": sha(spec_bytes)}}
        (HERE / f"fixture-recipe-{kind}.json").write_text(
            json.dumps(recipe, indent=2, ensure_ascii=False) + "\n")
        built.append(kind)
    return {"diagnostic_branches": built}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
