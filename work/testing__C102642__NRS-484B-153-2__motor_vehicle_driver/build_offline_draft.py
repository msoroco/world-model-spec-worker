"""Build five exact door-action diagnostic bundles for pinned offline proof."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
KINDS = ("open_near_overlap", "open_near_clear", "open_far_side", "board_near", "alight_near")

RUNNER = '''"""Exact door-action diagnostic entrypoint."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from site_contract import CASE_ACTIONS
from site_contract import read_packet, validate_site
from native_capture import CAMERAS, RATE_HZ, FRAME_COUNT
from native_runner import run_capture


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("case plan source changed")
    plan = json.loads(source)
    case = config["selected_case_id"]
    if case not in {row["case_id"] for row in plan["cases"]}:
        raise ValueError("selected case absent from exact plan")
    kind = case.removeprefix(config["assignment_id"] + "__")
    if kind not in CASE_ACTIONS or tuple(config["action"]) != CASE_ACTIONS[kind]:
        raise ValueError("selected door act/side differs")
    if config["rate_hz"] != RATE_HZ or config["frame_count"] != FRAME_COUNT or tuple(config["cameras"]) != CAMERAS:
        raise ValueError("original camera or duration profile differs")
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    case = check()
    if args.check:
        print("diagnostic door bundle passed: " + case)
        return
    if not args.output_dir or not args.host or not args.port:
        raise ValueError("Native host, port and output directory are required")
    survey_name = os.environ.get("SCENARIO_DOOR_SURVEY_PACKET")
    survey_hash = os.environ.get("SCENARIO_DOOR_SURVEY_SHA256")
    operator_name = os.environ.get("SCENARIO_DOOR_OPERATOR_MODULE")
    operator_hash = os.environ.get("SCENARIO_DOOR_OPERATOR_SHA256")
    if not all((survey_name, survey_hash, operator_name, operator_hash)):
        raise ValueError("original survey and source-hashed operator module are required")
    survey = Path(survey_name).resolve()
    packet = read_packet(survey, survey_hash)
    validate_site(packet, case.removeprefix(json.loads((Path(__file__).resolve().parent / "config.json").read_text())["assignment_id"] + "__"))
    operator = Path(operator_name).resolve()
    if hashlib.sha256(operator.read_bytes()).hexdigest() != operator_hash:
        raise ValueError("operator module source hash mismatch")
    spec = importlib.util.spec_from_file_location("door_operator", operator)
    if spec is None or spec.loader is None:
        raise ValueError("operator module cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    world = client.get_world()
    hooks = module.make_hooks(world, packet, case)
    required = {"actor_factory", "driver_act_controller", "original_observer"}
    if not isinstance(hooks, dict) or not required <= hooks.keys() or not all(callable(hooks[key]) for key in required):
        raise ValueError("operator module did not supply three Native hooks")
    map_reader = hooks.get("map_reader", lambda native_world: native_world.get_map().to_opendrive().encode("utf-8"))
    if not callable(map_reader):
        raise ValueError("operator map reader must be callable")
    try:
        result = run_capture(world, carla, survey_path=survey, survey_sha256=survey_hash,
                             case_id=case, output=Path(args.output_dir), map_reader=map_reader,
                             actor_factory=hooks["actor_factory"],
                             driver_act_controller=hooks["driver_act_controller"],
                             original_observer=hooks["original_observer"])
    except Exception as error:
        # The runtime retains a failed Native attempt only with an explicit
        # failure status. Never turn an incomplete acquisition into success.
        status = Path(args.output_dir) / "native-run-status.json"
        status.write_text(json.dumps({"errors": [str(error)], "case_id": case,
                                      "capture_complete": False}, sort_keys=True) + "\\n")
        raise
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
'''

TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_case_and_action(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(), json.loads((root / "config.json").read_text())["selected_case_id"])

    def test_refuses_diagnostic_native_capture(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "Native host, port"):
                runner.main()

    def test_native_requires_original_source_before_client_import(self):
        with patch("sys.argv", ["runner.py", "--output-dir", ".",
                                "--host", "localhost", "--port", "2000"]):
            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaisesRegex(ValueError, "original survey and source-hashed operator"):
                    runner.main()


if __name__ == "__main__":
    unittest.main()
'''


def build() -> None:
    plan_bytes = (HERE / "case-plan.json").read_bytes()
    exact = {row["case_id"] for row in json.loads(plan_bytes)["cases"]}
    from sys import path
    path.insert(0, str(HERE))
    from site_contract import CASE_ACTIONS
    rows = []
    for kind in KINDS:
        case = AID + "__" + kind
        if case not in exact:
            raise ValueError("selected exact case missing")
        config = {"law_id": "NRS-484B-153-2", "cell_id": "C102642",
                  "actor": "motor_vehicle_driver", "assignment_id": AID,
                  "selected_case_id": case, "action": CASE_ACTIONS[kind],
                  "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
                  "rate_hz": 20, "frame_count": 900,
                  "cameras": ["front", "rear", "left", "right"],
                  "diagnostic_only": True, "required_atoms": []}
        files = {"runner.py": RUNNER,
                 "site_contract.py": (HERE / "site_contract.py").read_text(),
                 "native_capture.py": (HERE / "native_capture.py").read_text(),
                 "carla_adapter.py": (HERE / "carla_adapter.py").read_text(),
                 "native_runner.py": (HERE / "native_runner.py").read_text(),
                 "door_interaction.py": (HERE / "door_interaction.py").read_text(),
                 "delivery_measure.py": (HERE / "delivery_measure.py").read_text(),
                 "delivery_audit.py": (HERE / "delivery_audit.py").read_text(),
                 "process_saved.py": (HERE / "process_saved.py").read_text(),
                 "compare_saved.py": (HERE / "compare_saved.py").read_text(),
                 "case-plan.json": plan_bytes.decode(),
                 "config.json": json.dumps(config, indent=2) + "\n",
                 "tests/test_bundle.py": TEST}
        construction = {"law_id": config["law_id"], "cell_id": config["cell_id"],
                        "actor": config["actor"], "case_id": case,
                        "entrypoint": "runner.py", "diagnostic_only": True,
                        "recording_description": {"status": "diagnostic_only_original_survey_pending",
                                                  "channels": config["cameras"]},
                        "files": [{"path": name, "content": content} for name, content in files.items()]}
        file = HERE / ("construction-" + kind + ".json")
        file.write_text(json.dumps(construction, indent=2) + "\n")
        rows.append({"case_id": case, "construction": file.name,
                     "construction_sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                     "candidate_risk": {"status": "physical", "reason": "Door articulation and boarding/alighting actor realization require original Native review; no failure-triggered fallback selected"}})
    (HERE / "execution-manifest.draft.json").write_text(json.dumps({"assignment_id": AID,
        "cases": rows, "status": "diagnostic_offline_only_surveyed_site_pending"}, indent=2) + "\n")
    print("built five exact diagnostic door-action constructions")


if __name__ == "__main__":
    build()
