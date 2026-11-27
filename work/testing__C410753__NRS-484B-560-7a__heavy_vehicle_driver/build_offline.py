"""Build seven exact source-gated heavy-vehicle railway construction bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import railway_7a as law

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
                with self.assertRaisesRegex(ValueError, "source-hashed reviewed railway site"):
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
    if {row["case_id"] for row in plan["cases"]} != {AID + "__" + name for name in law.CASE_AXES}:
        raise ValueError("exact railway case plan changed")
    source_files = ("runner.py", "native_capture.py", "native_output_bridge.py",
                    "railway_7a.py", "analysis.py", "case-plan.json")
    content = {name: (HERE / name).read_text() for name in source_files}
    (HERE / "tests/test_bundle.py").write_text(BUNDLE_TEST)
    content["tests/test_bundle.py"] = BUNDLE_TEST
    base_config = json.loads((HERE / "config.json").read_text())
    description = base_config["case"]["recording_description"]
    channels = description["channels"]
    entries = []
    for name in law.CASE_AXES:
        case_id = AID + "__" + name
        for candidate, approach_start in (("primary", 55.0), ("fallback1", 75.0)):
            config = dict(base_config, selected_case_id=case_id,
                          approach_start_m=approach_start,
                          plan_sha256=hashlib.sha256(plan_bytes).hexdigest())
            config["case"] = {"case_id": case_id, "recording_description": description}
            files = dict(content, **{"config.json": json.dumps(config, sort_keys=True, indent=2) + "\n"})
            construction = {
                "law_id": law.LAW, "cell_id": law.CELL, "actor": law.ACTOR,
                "case_id": case_id, "entrypoint": "runner.py",
                "recording_description": description,
                "measurement_plan": {"case_id": case_id,
                    "source_packets": ["site", "history", "frame_map"],
                    "procedure": "analysis.py", "legal_judgment": "unresolved"},
                "static_checks": ["reviewed original rail, road-profile, downstream-space and vehicle source hashes",
                                  "Native map, rail geometry, obstacle, undercarriage and heavy/coupled-unit readback",
                                  "900 original 20 Hz body, contact, control and four-camera frames"],
                "termination_rules": ["900 original Native ticks",
                                      "recorded actual trailing-end crossing or halt, pending local review"],
                "mechanisms": ["reviewed paved-road grade crossing with source-bound multiple-rail geometry",
                               "source-hashed downstream obstruction or actual road-profile contact",
                               "heavy/coupled-unit body and motion readback",
                               "four synchronized RGB cameras"],
                "files": [{"path": filename, "content": data} for filename, data in files.items()]}
            relative = Path("cases") / name / ("construction.json" if candidate == "primary"
                                                 else "fallback1/construction.json")
            path = HERE / relative
            write(path, construction)
            if name == next(iter(law.CASE_AXES)) and candidate == "primary":
                write(HERE / "config.json", config)
                write(HERE / "construction.json", construction)
            if candidate == "primary":
                entries.append({"case_id": case_id, "kind": "delivery",
                    "construction": str(relative), "construction_sha256": sha(path),
                    "candidate_risk": {"status": "physical",
                        "reason": "Long heavy/coupled vehicle may miss the source-reviewed rail position or the obstacle/contact event from a shorter approach; full body and road profile may fall outside camera coverage."},
                    "measurement_procedure": {"entrypoint": "analysis.py",
                                              "method": "source-bound original heavy/coupled trailing-end and cause observations"},
                    "acquisition": {channel["name"]: {
                        "entrypoint": "analysis.py",
                        "method": "Source-hashed original Native rail, body, obstacle/contact and control readback",
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
                    "trigger": {"source": "original 20 Hz heavy/coupled-unit body, rail, obstacle/contact and camera history",
                                "metric": "observed target halt/completion and complete four-view visibility",
                                "failure_condition": "primary misses intended physical event or complete body/profile camera coverage"}})
    write(HERE / "execution-manifest.json", {
        "format": "worker-execution-manifest", "assignment_id": AID,
        "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
        "cases": entries})
    return len(entries)


if __name__ == "__main__":
    print(build())
