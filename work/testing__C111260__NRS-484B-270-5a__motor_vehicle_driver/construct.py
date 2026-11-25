"""Build six exact text-only constructions from this assignment's reviewed code."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULES = ("runner.py", "analysis.py", "native_run.py", "native_site.py", "native_adapter.py",
           "native_cameras.py", "native_capture.py", "video_media.py",
           "cyclist_encounter.py", "saved_encounter.py", "tests/test_bundle.py")


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))
    for index, case in enumerate(plan["cases"]):
        case_id = case["case_id"]
        suffix = case_id.split("__")[-1]
        target = ROOT if index == 0 else ROOT / "cases" / suffix
        config = json.loads((target / "config.json").read_text(encoding="utf-8"))
        if config["selected_case_id"] != case_id:
            raise ValueError("exact case config differs")
        files = []
        for relative in MODULES:
            source = ROOT / relative
            files.append({"path": relative,
                          "source": "work/" + plan["assignment_id"] + "/" + relative,
                          "content": source.read_text(encoding="utf-8")})
        files.append({"path": "config.json", "content":
                      (target / "config.json").read_text(encoding="utf-8")})
        construction = {
            "law_id": plan["law_id"], "cell_id": plan["cell_id"],
            "actor": plan["actor"], "case_id": case_id,
            "entrypoint": "runner.py", "diagnostic_only": False,
            "recording_description": config["case"]["recording_description"],
            "measurement_plan": {"rate_hz": 20, "duration_s": 45,
                                 "required_channels": [c["name"] for c in
                                                       config["case"]["recording_description"]["channels"]]},
            "static_checks": ["exact source and case identity", "reviewed live waypoint and mounted rider asset",
                              "900 frame four camera source join"],
            "termination_rules": ["900 consecutive original Native ticks", "restore world and actors on every exit"],
            "mechanisms": ["source-gated motorist/rider Native controller", "synchronous four-camera RGB acquisition",
                           "saved-source measurement and independent review"],
            "files": files,
        }
        (target / "construction.json").write_text(json.dumps(construction, indent=2,
                                                                ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
