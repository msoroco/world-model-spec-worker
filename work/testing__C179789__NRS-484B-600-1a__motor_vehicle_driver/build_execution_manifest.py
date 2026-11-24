"""Build source-bound, exact-case CPU construction bundles.

The canonical manifest remains partial until reviewed numeric inputs and the
pinned offline, physical, and compatibility receipts exist.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MODULES = (
    "runner.py", "native_camera.py", "native_capture.py", "native_conditions.py",
    "native_control.py", "native_media.py", "native_scene.py",
    "native_count_probes.py", "native_count_capture.py",
    "prove_native_count_capture.py",
    "saved_conditions.py", "saved_measurement.py", "comparison_audit.py",
    "delivery_audit.py", "case-plan.json", "measurement-contract.json",
)
TESTS = tuple(sorted(path.relative_to(HERE).as_posix() for path in
                     (HERE / "tests").glob("test_*.py")
                     if path.name not in ("test_branch_plan.py", "test_bind_semantic_packet.py")))
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
    proposal = json.loads((HERE / "proposals/cases.json").read_text(encoding="utf-8"))
    by_id = {case["case_id"]: case for case in proposal["cases"]}
    entries = []
    for planned in plan["cases"]:
        case_id = planned["case_id"]
        case = by_id[case_id]
        suffix = case_id.rsplit("__", 1)[-1]
        folder = HERE / "constructions"
        folder.mkdir(exist_ok=True)
        config = {
            "assignment_id": plan["assignment_id"], "selected_case_id": case_id,
            "law_id": plan["law_id"], "cell_id": plan["cell_id"],
            "actor": plan["actor"], "rate_hz": 20, "duration_s": 45,
            "cameras": [{"name": name, "width": width, "height": height,
                         "pose_strategy": "reviewed source packet and original Native rig",
                         "fov_deg": 90} for name, width, height in CAMERAS],
            "capture_provenance": "original Native samples required",
            "required_atoms": [], "source_packets": [],
            "case": case, "numeric_binding_status": "reviewed_source_pending",
            "physical_acceptance_claimed": False,
        }
        files = []
        for relative in MODULES + TESTS:
            source = HERE / relative
            files.append({"path": relative, "source": source.relative_to(REPO).as_posix(),
                          "content": source.read_text(encoding="utf-8")})
        files.append({"path": "config.json", "content": json.dumps(config, indent=2) + "\n"})
        construction = {
            "case_id": case_id, "cell_id": plan["cell_id"],
            "law_id": plan["law_id"], "actor": plan["actor"],
            "entrypoint": "runner.py", "files": files,
            "recording_description": case["recording_description"],
            "measurement_plan": {"entrypoint": "saved_measurement.py",
                                 "sources": ["original-conditions.jsonl", "trace.jsonl",
                                             "video_frames.jsonl", "overview.mkv",
                                             "approach.mkv", "reference_corner.mkv",
                                             "driver_reference.mkv"], "case_id": case_id},
            "static_checks": ["exact case and camera configuration",
                              "retained source hashes and reviewed numeric decision pending"],
            "termination_rules": ["900 Native frames maximum",
                                  "stop on source, frame, or restoration error"],
            "mechanisms": ["source-bound original Native scene and controls",
                           "four-view capture and saved-source measurement"],
            "status": "partial: reviewed numerical inputs and full receipts pending",
        }
        path = folder / f"{suffix}.json"
        path.write_text(json.dumps(construction, indent=2) + "\n", encoding="utf-8")
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("construction exceeds returned-file limit")
        recipe = (HERE if suffix == "reference" else HERE / "diagnostics" / suffix)
        recipe = recipe / "diagnostic-recipe.json"
        if not recipe.is_file():
            raise ValueError("missing exact diagnostic recipe: " + suffix)
        entries.append({
            "case_id": case_id, "kind": "delivery",
            "construction": path.relative_to(HERE).as_posix(),
            "construction_sha256": sha(path),
            "measurement_contract": "measurement-contract.json",
            "measurement_procedure": {"entrypoint": "saved_measurement.py"},
            "fixture_recipe": recipe.relative_to(REPO).as_posix(),
            "native_handoff": {"python_env_var": "CARLA_PYTHON",
                               "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
            "physical_risk_assessment": planned["physical_risk_assessment"],
            "status": "partial_offline_and_compatibility_pending",
        })
    manifest = {"format": "worker-execution-manifest",
                "assignment_id": plan["assignment_id"],
                "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
                "cases": entries, "status": "partial_cpu_construction_only"}
    reference = json.loads((HERE / "constructions/reference.json").read_text(encoding="utf-8"))
    (HERE / "construction.json").write_text(json.dumps(reference, indent=2) + "\n",
                                             encoding="utf-8")
    config = json.loads(next(file["content"] for file in reference["files"]
                             if file["path"] == "config.json"))
    config["supported_case_ids"] = [entry["case_id"] for entry in entries]
    (HERE / "config.json").write_text(json.dumps(config, indent=2) + "\n",
                                       encoding="utf-8")
    (HERE / "execution-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    result = build()
    print(json.dumps({"case_count": len(result["cases"]),
                      "status": result["status"]}, sort_keys=True))
