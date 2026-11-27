"""Build exact source-gated School-Xing heavy-vehicle delivery bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import school_crossing as school


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
BUNDLE_TEST = '''import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner


class BundleTests(unittest.TestCase):
    def test_exact_case(self):
        selected, config = runner.check()
        self.assertEqual(selected, config["selected_case_id"])

    def test_reviewed_sources_required_before_carla(self):
        with patch("sys.argv", ["runner.py", "--host", "localhost", "--port", "2000", "--output-dir", "attempt"]):
            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaisesRegex(ValueError, "source-hashed reviewed School-Xing site"):
                    runner.main()


if __name__ == "__main__":
    unittest.main()
'''


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan_bytes = (HERE / "case-plan.json").read_bytes()
    plan = json.loads(plan_bytes)
    exact = {row["case_id"] for row in plan["cases"]}
    if exact != {AID + "__" + case.name for case in school.CASES}:
        raise ValueError("exact frozen School-Xing case plan changed")
    source_files = ("runner.py", "native_capture.py", "native_output_bridge.py",
                    "school_crossing.py", "analysis.py", "case-plan.json")
    content = {name: (HERE / name).read_text() for name in source_files}
    (HERE / "tests/test_bundle.py").write_text(BUNDLE_TEST)
    content["tests/test_bundle.py"] = BUNDLE_TEST
    base_config = json.loads((HERE / "config.json").read_text())
    channels = base_config["case"]["recording_description"]["channels"]
    description = base_config["case"]["recording_description"]
    entries = []
    for case in school.CASES:
        case_id = AID + "__" + case.name
        for candidate, approach_start in (("primary", 55.0), ("fallback1", 75.0)):
            config = dict(base_config, selected_case_id=case_id,
                          approach_start_m=approach_start,
                          plan_sha256=hashlib.sha256(plan_bytes).hexdigest())
            config["case"] = {"case_id": case_id, "recording_description": description}
            files = dict(content, **{"config.json": json.dumps(config, sort_keys=True,
                                                                  indent=2) + "\n"})
            construction = {
                "law_id": school.LAW, "cell_id": "C422976",
                "actor": "heavy_vehicle_driver", "case_id": case_id,
                "entrypoint": "runner.py", "recording_description": description,
                "measurement_plan": {"case_id": case_id,
                    "source_packets": ["site", "history", "frame_map"],
                    "procedure": "analysis.py", "legal_judgment": "unresolved"},
                "static_checks": ["reviewed original municipal, sign, crossing, person and heavy-vehicle source hashes",
                                  "Native map, sign display, crossing and route readback",
                                  "900 original 20 Hz participant and four-camera frames"],
                "termination_rules": ["900 original Native ticks",
                                      "recorded physical crossing entry or hold, pending local review"],
                "mechanisms": ["reviewed school-vicinity two-way intersection and physical crossing",
                               "source-hashed School-Xing sign and Native operator",
                               "heavy-vehicle approach and independent person control",
                               "four synchronized RGB cameras"],
                "files": [{"path": name, "content": data} for name, data in files.items()]}
            relative = Path("cases") / case.name / ("construction.json" if candidate == "primary"
                                                       else "fallback1/construction.json")
            path = HERE / relative
            write(path, construction)
            if case == school.CASES[0] and candidate == "primary":
                write(HERE / "config.json", config)
                write(HERE / "construction.json", construction)
            if candidate == "primary":
                entries.append({"case_id": case_id, "kind": "delivery",
                    "construction": str(relative), "construction_sha256": sha(path),
                    "candidate_risk": {"status": "physical",
                        "reason": "Heavy vehicle may fail to hold or enter with a shorter approach, and the sign/person may be outside camera framing."},
                    "measurement_procedure": {"entrypoint": "analysis.py",
                                              "method": "source-bound original vehicle/person crossing entry"},
                    "acquisition": {channel["name"]: {
                        "entrypoint": "analysis.py",
                        "method": "Source-hashed original Native participant, crossing and sign readback",
                        "evidence": "channels/" + channel["name"] + ".jsonl"}
                        for channel in channels},
                    "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                       "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
                    "candidates": []})
            else:
                entries[-1]["candidates"].append({
                    "id": "fallback1", "construction": str(relative),
                    "construction_sha256": sha(path),
                    "changed_knobs": ["reviewed heavy-vehicle approach start 75 m instead of 55 m for all linked cases"],
                    "trigger": {"source": "original 20 Hz heavy-vehicle front, person and camera history",
                                "metric": "observed target entry or hold and complete four-view visibility",
                                "failure_condition": "primary misses target entry/hold or physical camera coverage"}})
    write(HERE / "execution-manifest.json", {
        "format": "worker-execution-manifest", "assignment_id": AID,
        "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
        "cases": entries})
    return len(entries)


if __name__ == "__main__":
    print(build())
