"""Regenerate seven exact inline CPU constructions from current local sources.

Run only while the assignment remains partial. Proof receipts bind each output
hash and must be regenerated after any source edit.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCES = (
    "runner.py", "analysis.py", "live_entrypoint.py", "live_crosswalk.py",
    "carla_scene_factory.py", "carla_adapter.py", "native_setup.py",
    "native_capture.py", "crosswalk.py", "saved_measurement.py",
    "saved_media_audit.py", "saved_delivery.py", "saved_comparison.py",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def description(plan):
    return {
        "channels": [
            {"name": row["name"], "unit": "structured record",
             "sampling_rate_hz": 20, "method": row["source"],
             "time_window": "entire 30-second original attempt",
             "reference_frame": "original Native frame and time",
             "uncertainty": "20 Hz sampling, actor geometry and source review"}
            for row in plan["observations"]],
        "context_inputs": [
            {"name": "reviewed_original_site", "unit": "structured record",
             "method": "Source-gated map, crosswalk, directional-half and device survey"},
            {"name": "reviewed_exception_context", "unit": "structured record",
             "method": "Independent source-backed applicability review"}],
        "limitations": [
            "Physical motion and four-camera pixel visibility need original Native review.",
            "Legal yielding, opposite-half danger and statutory exceptions remain unresolved."],
    }


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    original = json.loads((ROOT / "config.json").read_text())
    recording = description(plan)
    manifest = {
        "format": "worker-execution-manifest",
        "assignment_id": plan["assignment_id"],
        "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
        "cases": [],
    }
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        scene_path = ROOT / "scenes" / (suffix + ".json")
        scene = json.loads(scene_path.read_text())
        if scene["case_id"] != case_id:
            raise ValueError("scene identity differs: " + suffix)
        config = dict(original)
        config["selected_case_id"] = case_id
        config["scene_sha256"] = sha(scene_path)
        config["case"] = {"case_id": case_id,
                          "recording_description": recording}
        config_text = json.dumps(config, indent=2) + "\n"
        if suffix == "destination_occupied_absent":
            write(ROOT / "config.json", config)
            (ROOT / "scene.json").write_bytes(scene_path.read_bytes())
        files = []
        for name in SOURCES:
            source = ROOT / name
            files.append({"path": name, "source": str(source.relative_to(REPO)),
                          "content": source.read_text()})
        files.extend([
            {"path": "config.json", "content": config_text,
             **({"source": str((ROOT / "config.json").relative_to(REPO))}
                if suffix == "destination_occupied_absent" else {})},
            {"path": "scene.json", "content": scene_path.read_text(),
             "source": str(scene_path.relative_to(REPO))},
            {"path": "tests/test_bundle.py",
             "content": (ROOT / "bundle_tests/test_bundle.py").read_text(),
             "source": str((ROOT / "bundle_tests/test_bundle.py").relative_to(REPO))},
        ])
        construction = {
            "law_id": plan["law_id"], "cell_id": plan["cell_id"],
            "actor": plan["actor"], "case_id": case_id,
            "entrypoint": "runner.py", "diagnostic_only": True,
            "recording_description": recording,
            "measurement_plan": {
                "rate_hz": 20, "duration_s": 30,
                "required_channels": [row["name"] for row in plan["observations"]],
                "source_method": "original Native frames, sealed files and independent saved review"},
            "static_checks": ["exact scene/source identity", "four-camera timing",
                              "source-gated map, route, device and exception review"],
            "termination_rules": ["600 original 20 Hz ticks", "stop on source or camera failure"],
            "mechanisms": ["bounded left-turn and pedestrian route controller",
                           "original four-camera frame map", "source-sealed saved measurements"],
            "files": files,
        }
        construction_path = (ROOT / "construction.json" if
                             suffix == "destination_occupied_absent" else
                             ROOT / "cases" / suffix / "construction.json")
        write(construction_path, construction)
        fallback_scene = dict(scene, engineering_target_speed_mps=2.5)
        fallback_scene_path = ROOT / "cases" / suffix / "fallback1-scene.json"
        write(fallback_scene_path, fallback_scene)
        fallback_config = dict(config, scene_sha256=sha(fallback_scene_path),
                               engineering_speed_note="slower 2.5 m/s same-route observation fallback")
        fallback_config_path = ROOT / "cases" / suffix / "fallback1-config.json"
        write(fallback_config_path, fallback_config)
        fallback = dict(construction)
        fallback["files"] = [
            ({**item, "content": fallback_config_path.read_text(),
              "source": str(fallback_config_path.relative_to(REPO))}
             if item["path"] == "config.json" else
             {**item, "content": fallback_scene_path.read_text(),
              "source": str(fallback_scene_path.relative_to(REPO))}
             if item["path"] == "scene.json" else item)
            for item in files]
        fallback_path = ROOT / "cases" / suffix / "fallback1-construction.json"
        write(fallback_path, fallback)
        manifest["cases"].append({
            "case_id": case_id,
            "construction": str(construction_path.relative_to(ROOT)),
            "construction_sha256": sha(construction_path),
            "kind": "delivery",
            "candidate_risk": {"status": "physical",
                               "reason": case["physical_risk_assessment"]["risk"]},
            "candidates": [{"id": "fallback1",
                            "construction": str(fallback_path.relative_to(ROOT)),
                            "construction_sha256": sha(fallback_path),
                            "trigger": {"source": "original Native 20 Hz ego and pedestrian frame join",
                                        "metric": "pedestrian crossing observation and ego approach overlap frames",
                                        "failure_condition": "Primary 4 m/s turn produces insufficient overlap or blur for independent source review"},
                            "changed_knobs": ["same-route engineering target speed: 4.0 to 2.5 m/s"]}],
            "measurement_procedure": {"entrypoint": "analysis.py"},
            "native_handoff": {"python_env_var": "CARLA_PYTHON",
                               "host_env_var": "CARLA_HOST",
                               "port_env_var": "CARLA_PORT",
                               "site_root_env_var": "C111610_SITE_ROOT"},
        })
    write(ROOT / "execution-manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    result = build()
    print(len(result["cases"]), "exact inline constructions")
