"""Materialize exact right-curb primary and same-curb fallback bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_semantic import recording_description

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PLAN_BYTES = (ROOT / "case-plan.json").read_bytes()
PLAN = json.loads(PLAN_BYTES)
ASSIGNMENT = PLAN["assignment_id"]
FILES = ("runner.py", "native_acquisition.py", "finalize_native.py",
         "curb_construction.py", "curb_geometry.py", "analysis.py",
         "audit_original_attempt.py", "audit_comparisons.py",
         "case-plan.json", "tests/test_curb_geometry.py", "tests/test_native_acquisition.py")


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _cameras():
    return [
        {"name": "overview", "width": 1920, "height": 1080, "fov_deg": 75,
         "pose_strategy": "surveyed public highway, ordinary motor vehicle and adjacent right curb"},
        {"name": "approach", "width": 1280, "height": 720, "fov_deg": 75,
         "pose_strategy": "right wheel and adjacent curb spacing through stopped or parked interval"},
        {"name": "reference_corner", "width": 1280, "height": 720, "fov_deg": 75,
         "pose_strategy": "curb tangent, vehicle body and wheel-axis alignment"},
        {"name": "driver_reference", "width": 1280, "height": 720, "fov_deg": 75,
         "pose_strategy": "original driver, parking control and stopped state"},
    ]


def build():
    description = recording_description()
    ids = [row["case_id"] for row in PLAN["cases"]]
    entries = []
    for index, row in enumerate(PLAN["cases"]):
        variant = row["variant"]
        targets = []
        for candidate in ("primary", "fallback1"):
            base = ROOT / "cases" / variant
            if candidate == "fallback1":
                base /= candidate
            config = {
                "assignment_id": ASSIGNMENT, "law_id": PLAN["law_id"],
                "cell_id": PLAN["cell_id"], "actor": PLAN["actor"],
                "selected_case_id": row["case_id"], "variant": variant,
                "supported_case_ids": ids,
                "plan_sha256": hashlib.sha256(PLAN_BYTES).hexdigest(),
                "fallback": candidate == "fallback1",
                "duration_s": 45, "rate_hz": 20, "frame_count": 900,
                "cameras": _cameras(), "diagnostic_only": True,
                "required_atoms": [], "source_packets": [],
                "case": {"case_id": row["case_id"], "recording_description": description},
                "recording_description": description,
                "source_requirements": [
                    "source-hashed OpenDRIVE, public highway, adjacent right-curb survey, local ordinance and DOT status",
                    "ordinary motor vehicle blueprint and actual wheelbase/source review",
                    "900 original 20 Hz right-wheel, parking-control and four-camera frames"],
            }
            _write(base / "config.json", config)
            files = []
            for name in FILES:
                source_name = ("test_curb_geometry.py" if name == "tests/test_curb_geometry.py" else
                               "test_native_acquisition.py" if name == "tests/test_native_acquisition.py" else name)
                source = ROOT / source_name
                files.append({"path": name, "source": "work/" + ASSIGNMENT + "/" + source_name,
                              "content": source.read_text()})
            files.append({"path": "config.json", "source": "work/" + ASSIGNMENT + "/" +
                          str((base / "config.json").relative_to(ROOT)),
                          "content": (base / "config.json").read_text()})
            construction = {
                "status": "draft", "case_id": row["case_id"], "law_id": PLAN["law_id"],
                "cell_id": PLAN["cell_id"], "actor": PLAN["actor"],
                "entrypoint": "runner.py", "files": files,
                "recording_description": description,
                "measurement_plan": {"case_id": row["case_id"],
                                     "procedure": "analysis.py",
                                     "source_packets": ["reviewed_right_curb_site", "original_wheel_motion",
                                                        "original_frame_map", "four_original_camera_streams"],
                                     "legal_judgment": "unresolved"},
                "mechanisms": ["surveyed curb-tangent right-wheel placement from actual reviewed wheelbase",
                               "original Native wheel/parking-control readback and source seal",
                               "same-tick 900-frame four-camera capture and owner cleanup"],
                "static_checks": ["exact law, cell, actor, variant and plan hash",
                                  "reviewed highway, curb, ordinance and blueprint sources",
                                  "actual Native map identity and wheel geometry readback"],
                "termination_rules": ["900 original Native ticks at 20 Hz",
                                      "fail closed on missing source, wheel, camera or incomplete original activity"],
            }
            _write(base / "construction.json", construction)
            targets.append((str((base / "construction.json").relative_to(ROOT)), _sha(base / "construction.json")))
            if index == 0 and candidate == "primary":
                _write(ROOT / "config.json", config)
                _write(ROOT / "construction.json", construction)
        entries.append({
            "case_id": row["case_id"], "kind": "delivery",
            "construction": targets[0][0], "construction_sha256": targets[0][1],
            "measurement_contract": "measurement-" + variant + ".json",
            "measurement_procedure": {"entrypoint": "analysis.py",
                                      "method": "source-sealed original right-wheel and parking-control geometry"},
            "native_handoff": {"host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT",
                               "python_env_var": "CARLA_PYTHON"},
            "candidate_risk": row["candidate_risk"],
            "candidates": [{"id": "fallback1", "construction": targets[1][0],
                            "construction_sha256": targets[1][1],
                            "changed_knobs": ["shift reviewed parking station 0.5 m along the same surveyed right curb"],
                            "trigger": {"source": "original Native wheel and four-camera history",
                                        "metric": "wheel clearance, camera coverage and curb pose",
                                        "failure_condition": "primary surveyed station cannot realize complete right-wheel and curb visibility"}}],
        })
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": _sha(REPO / "runtime/SOURCE-MANIFEST.json"),
                "cases": entries, "comparisons": PLAN["comparisons"]}
    _write(ROOT / "execution-manifest.json", manifest)
    return len(entries)


if __name__ == "__main__":
    print(build())
