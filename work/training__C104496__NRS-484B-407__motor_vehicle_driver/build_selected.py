"""Assemble exact C104496 selected CPU constructions from reviewed sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = (("probe_01", "crest"), ("probe_02", "crest"),
         ("probe_03", "curve"))
CANDIDATES = ("primary", "fallback1", "fallback2")
CAMERAS = [
    {"name": "overview", "width": 1920, "height": 1080, "fov_deg": 80,
     "pose_strategy": "fixed elevated view over the authored reversal interval"},
    {"name": "approach", "width": 1280, "height": 720, "fov_deg": 80,
     "pose_strategy": "fixed source-direction observer at the western 500-foot station"},
    {"name": "reference_corner", "width": 1280, "height": 720, "fov_deg": 80,
     "pose_strategy": "fixed opposing-direction observer at the eastern 500-foot station"},
    {"name": "driver_reference", "width": 1280, "height": 720, "fov_deg": 80,
     "pose_strategy": "fixed auxiliary road and body view near the reversal interval"},
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(value):
    return json.dumps(value, indent=2, allow_nan=False) + "\n"


def build():
    proposal = json.loads((HERE / "proposals/cases.json").read_text())
    case_ids = [HERE.name + "__" + suffix for suffix, _ in CASES]
    entries = []
    for suffix, branch in CASES:
        case_id = HERE.name + "__" + suffix
        case = next(item for item in proposal["cases"] if item["case_id"] == case_id)
        selections = []
        for candidate in CANDIDATES:
            draft_path = HERE / "native" / branch / "runtime-drafts" / suffix / candidate / "construction.json"
            draft = json.loads(draft_path.read_text())
            files = draft["files"]
            by_path = {item["path"]: item for item in files}
            if branch == "curve":
                source_bundle = HERE / "native/curve/drafts" / suffix / candidate
                for name in ("assignment-source.json", "case-plan.json",
                             "curve.xodr", "config.json", "requested-tracks.jsonl"):
                    by_path[name] = {"path": name,
                                     "content": (source_bundle / name).read_text()}
            cfg = json.loads(by_path["config.json"]["content"])
            cfg.update({"cell_id": "C104496", "law_id": "NRS-484B-407",
                        "actor": "motor_vehicle_driver", "duration_s": 35,
                        "selected_case_id": case_id,
                        "supported_case_ids": case_ids,
                        "case": {"case_id": case_id},
                        "required_atoms": [], "source_packets": [],
                        "cameras": CAMERAS,
                        "status": "selected_for_delivery_preparation"})
            by_path["config.json"]["content"] = dump(cfg)
            if branch == "crest":
                runner = by_path["capture.py"]["content"]
            else:
                nested = "work/" + HERE.name + "/native/curve"
                runner = ("import runpy\nimport sys\nfrom pathlib import Path\n"
                          "source = Path(__file__).resolve().parent / " + repr(nested) + "\n"
                          "sys.path.insert(0, str(source))\n"
                          "runpy.run_path(str(source / 'capture.py'), run_name='__main__')\n")
            by_path["runner.py"] = {"path": "runner.py", "content": runner}
            by_path["finalize.py"] = {"path": "finalize.py",
                "content": (HERE / "native/finalize.py").read_text()}
            construction = {"case_id": case_id, "cell_id": "C104496",
                "law_id": "NRS-484B-407", "actor": "motor_vehicle_driver",
                "entrypoint": "runner.py", "files": list(by_path.values()),
                "recording_description": case["recording_description"],
                "measurement_plan": ["case-specific saved ray, grade and turn source joins"],
                "static_checks": ["authored road/lane geometry", "exact 700-frame request"],
                "termination_rules": ["700 joined 20 Hz frames", "abort on missing original source"],
                "mechanisms": ["three-point reversal request", "two-direction observer rays"],
                "status": "selected_cpu_construction_physical_unverified"}
            path = HERE / "selected" / suffix / candidate / "construction.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(dump(construction))
            selections.append({"id": candidate,
                               "construction": str(path.relative_to(HERE)),
                               "construction_sha256": sha(path)})
        entries.append({"case_id": case_id,
                        "construction": selections[0]["construction"],
                        "construction_sha256": selections[0]["construction_sha256"],
                        "candidates": selections[1:],
                        "candidate_risk": {"status": "physical",
                            "reason": "Original body-ray visibility, camera recognition, "
                                      "and full physical reversal remain unverified."}})
    manifest = {"format": "c104496-selected-cpu-construction-manifest-v1",
                "assignment_id": HERE.name, "cases": entries,
                "selected_case_count": 3, "original_physical_proven": False}
    path = HERE / "selected-construction-manifest.json"
    path.write_text(dump(manifest))
    return manifest


if __name__ == "__main__":
    print(json.dumps({"cases": len(build()["cases"]), "candidates": 9,
                      "original_physical_proven": False}))
