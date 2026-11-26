"""Build exact source-gated primary and fallback Native signal bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import native_signal as signal


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))
BUNDLE_TEST = '''import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner

class BundleTests(TestCase):
    def test_exact_case(self):
        self.assertEqual(runner.check()[0]["selected_case_id"],
                         json.loads((runner.HERE / "config.json").read_text())["selected_case_id"])

    def test_reviewed_site_required_before_carla(self):
        with patch("sys.argv", ["runner.py", "--host", "localhost", "--port", "2000",
                                "--output-dir", "attempt"]):
            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaisesRegex(ValueError, "source-hashed reviewed signal site"):
                    runner.main()
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def build():
    plan_bytes = (HERE / "case-plan.json").read_bytes()
    plan = json.loads(plan_bytes)
    exact = {signal.ASSIGNMENT + "__" + item.name for item in signal.CASES}
    if {row["case_id"] for row in plan["cases"]} != exact:
        raise ValueError("exact frozen inoperative-signal cases changed")
    if len(plan["comparisons"]) != 5:
        raise ValueError("exact controlled comparison count changed")
    source_files = ("runner.py", "native_signal.py", "native_capture.py",
                    "native_output_bridge.py", "inoperative_signal.py",
                    "analysis.py", "case-plan.json")
    content = {name: (HERE / name).read_text() for name in source_files}
    (HERE / "tests").mkdir(exist_ok=True)
    (HERE / "tests/test_bundle.py").write_text(BUNDLE_TEST)
    entries = []
    for case in signal.CASES:
        full_id = signal.ASSIGNMENT + "__" + case.name
        channels = [{"name": row["name"], "unit": "structured",
                     "sampling_rate_hz": signal.RATE_HZ,
                     "method": row["method"], "time_window": "all 900 original ticks",
                     "reference_frame": "reviewed Native map and original world",
                     "uncertainty": "actual physical Native realization pending"}
                    for row in plan["observations"]]
        description = {
            "channels": channels,
            "context_inputs": [{"name": "reviewed_signal_site", "unit": "source",
                                "method": "source-hashed installation, governance, head cover, operation, stop hierarchy, through highway and sightline"}],
            "limitations": ["Cautious proceeding remains a source-grounded legal review; no speed cutoff is invented.",
                            "CPU diagnostics are not original Native physical acceptance."]}
        config = {"assignment_id": signal.ASSIGNMENT, "law_id": "NRS-484B-250-4",
                  "cell_id": "C24757", "actor": "motor_vehicle_driver",
                  "selected_case_id": full_id, "supported_case_ids": sorted(exact),
                  "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
                  "rate_hz": signal.RATE_HZ, "duration_s": 45,
                  "required_atoms": [], "source_packets": [],
                  "cameras": [{"name": view, "width": width, "height": height,
                               "fov_deg": 80,
                               "pose_strategy": "reviewed blind approach, signal head and stop reference"}
                              for view, width, height in CAMERAS],
                  "case": {"case_id": full_id,
                           "recording_description": description}}
        for candidate, distance in (("primary", 12.0), ("fallback1", 18.0)):
            config["brake_distance_m"] = distance
            files = dict(content)
            files["config.json"] = json.dumps(config, sort_keys=True, indent=2) + "\n"
            files["tests/test_bundle.py"] = BUNDLE_TEST
            construction = {
                "law_id": "NRS-484B-250-4", "cell_id": "C24757",
                "actor": "motor_vehicle_driver", "case_id": full_id,
                "entrypoint": "runner.py", "recording_description": description,
                "measurement_plan": {"case_id": full_id,
                                     "source_packets": ["site", "ego_history",
                                                        "other_history", "frame_map"],
                                     "procedure": "analysis.py",
                                     "legal_judgment": "unresolved"},
                "static_checks": ["reviewed signal installation, uncovering, governance and inoperability sources",
                                  "source-hashed stop hierarchy and distinct interacting vehicle route",
                                  "900 synchronized 20 Hz ego/other and four original RGB views"],
                "termination_rules": ["900 original Native ticks",
                                      "observed ego intersection entry and post-stop interaction"],
                "mechanisms": ["source-gated Native operator and reviewed OpenDRIVE",
                               "two distinct Native motor vehicles and physical controller",
                               "original signal readback at entry and four RGB callbacks"],
                "files": [{"path": name, "content": data} for name, data in files.items()]}
            rel = Path("cases") / case.name / ("construction.json" if candidate == "primary"
                                               else "fallback1/construction.json")
            path = HERE / rel
            write(path, construction)
            if case == signal.CASES[0] and candidate == "primary":
                write(HERE / "config.json", config)
                write(HERE / "construction.json", construction)
            if candidate == "primary":
                entries.append({
                    "case_id": full_id, "kind": "delivery",
                    "construction": str(rel), "construction_sha256": sha(path),
                    "candidate_risk": {"status": "physical",
                                       "reason": "Native brake timing, signal readback or blind sightline may miss required original evidence."},
                    "measurement_procedure": {"entrypoint": "analysis.py",
                                              "method": "saved original signal, front, stop and other-vehicle measurement"},
                    "acquisition": {channel["name"]: {
                        "entrypoint": "analysis.py", "method": channel["method"],
                        "evidence": "channels/" + channel["name"] + ".jsonl"}
                        for channel in channels},
                    "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                       "host_env_var": "CARLA_HOST",
                                       "port_env_var": "CARLA_PORT"},
                    "candidates": []})
            else:
                entries[-1]["candidates"].append({
                    "id": "fallback1", "construction": str(rel),
                    "construction_sha256": sha(path),
                    "changed_knobs": ["source-gated brake approach distance 18 m instead of 12 m"],
                    "trigger": {"source": "original 20 Hz front/speed and signal readback",
                                "metric": "cessation location and entry signal state",
                                "failure_condition": "primary Native stop, timing or sightline target not physically realized"}})
        contract_path = HERE / "cases" / case.name / "measurement-contract.json"
        inputs = ["site.json", "ego-history.json", "other-history.json", "frame-map.json"]
        output_keys = ("signal_at_entry", "stop_reference_and_cessation",
                       "other_vehicle_priority", "cautious_proceeding_context")
        write(contract_path, {
            "format": "worker-measurement-contract", "case_id": full_id,
            "requirements": [{"disposition_index": index,
                              "requirement": plan["requirement_dispositions"][index]["requirement"],
                              "source": plan["requirement_dispositions"][index]["source"],
                              "inputs": inputs, "kind": "measured", "method": "measure",
                              "output_key": output_keys[index], "value_type": "object"}
                             for index in range(4)],
            "negative": {"remove": ["other-history.json"],
                         "error_contains": "Missing required source: other-history.json"}})
        entries[-1]["measurement_contract"] = str(contract_path.relative_to(HERE))
        entries[-1]["fixture_recipe"] = str(
            (HERE / "cases" / case.name / "fixture-recipe.json").relative_to(REPO))
    write(HERE / "execution-manifest.json", {
        "format": "worker-execution-manifest", "assignment_id": signal.ASSIGNMENT,
        "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
        "cases": entries})
    return len(entries)


if __name__ == "__main__":
    print(build())
