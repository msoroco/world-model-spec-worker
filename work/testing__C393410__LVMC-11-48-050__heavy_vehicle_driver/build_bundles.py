"""Build exact source-gated nighttime heavy-vehicle constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MODULES = ("runner.py", "native_entry.py", "route_adapter.py", "restriction_measure.py", "analysis.py")
OFFLINE_TEST = '''import json
import unittest
from pathlib import Path
from runner import check

class SelectedNightTruckOffline(unittest.TestCase):
    def test_exact_source_gate(self):
        root = Path(__file__).resolve().parents[1]
        selected = check(root)
        self.assertEqual(selected['case_id'], json.loads((root / 'config.json').read_text())['selected_case_id'])
        self.assertIn('unladen', selected['source_gate'])

if __name__ == '__main__':
    unittest.main()
'''


def write(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> list[dict]:
    plan = json.loads((HERE / "case-plan.json").read_text())
    ids = [row["case_id"] for row in plan["cases"]]
    channel_definitions = (
        ("ego_operation", "state", "original 20 Hz ego actor, motion and road identity"),
        ("actual_unladen_weight", "lb", "vehicle-specific original unladen-weight documentary source"),
        ("local_civil_time", "local civil time", "UTC clock and timezone-qualified original civil-time source"),
        ("residence_district", "source", "municipal frontage and business-exclusion district review"),
        ("street_designation", "source", "authoritative truck-route extent and same-frame street road ID"),
        ("written_permit", "source", "DPW written application/issued permit, applicant, vehicle and every condition"))
    description = {"channels": [{"name": name, "unit": unit, "sampling_rate_hz": 20,
        "method": method, "time_window": "900 original frames",
        "reference_frame": "source-reviewed original C393410 street network",
        "uncertainty": "original physical source realization pending"}
        for name, unit, method in channel_definitions],
        "context_inputs": [{"name": "reviewed_night_truck_site", "unit": "source",
            "method": "SHA-bound original municipal district, route, vehicle, local clock and DPW administrative review"}],
        "limitations": ["Heavy-vehicle appearance does not establish actual unladen weight.",
            "A written application does not itself establish an issued written permit.",
            "Worker retains legal uncertainty about time endpoints and permit conditions."]}
    entries = []
    for case in plan["cases"]:
        cid = case["case_id"]
        short = cid.split("__")[-1]
        folder = HERE / "cases" / short
        config = {"law_id": plan["law_id"], "cell_id": plan["cell_id"],
            "actor": plan["actor"], "selected_case_id": cid,
            "supported_case_ids": ids, "required_atoms": [], "source_packets": [],
            "rate_hz": 20, "duration_s": 45,
            "cameras": [{"name": name, "width": dims[0], "height": dims[1],
                "fov_deg": 75, "pose_strategy": "source-reviewed original street and truck-route context view"}
                for name, dims in (("overview", (1920, 1080)), ("approach", (1280, 720)),
                                   ("reference_corner", (1280, 720)), ("driver_reference", (1280, 720)))],
            "physical_completion": {"criterion": "travel_progress", "motion_source": "trace.jsonl",
                "position_key": "position_m", "minimum_progress_m": 5.0, "minimum_samples": 3,
                "engineering_tolerances_not_legal": True,
                "completion_goal_method": "Original route progress proxy; independent audit verifies physical operation on reviewed street."},
            "case": {"case_id": cid,
                "physical_target": "source-reviewed 45-second operation or movement on exact street with unchanged selected condition",
                "recording_description": description}}
        spec = {"case_id": cid,
            "target_unladen_lb": case["target_unladen_lb"],
            "target_local_time": case["target_local_time"],
            "target_district": case["target_district"],
            "target_street_class": case["target_street_class"],
            "target_permit_status": case["target_permit_status"],
            "source_status": "reviewed_original_night_truck_packet_required_at_capture"}
        write(folder / "config.json", config)
        write(folder / "case-spec.json", spec)
        for candidate, speed in (("primary", 4.0), ("fallback1", 3.0)):
            controller = {"target_speed_mps": speed,
                "source": "predeclared road tracking with same-frame original road-ID and vehicle identity readback",
                "physical_acceptance": False}
            controller_name = "controller-" + candidate + ".json"
            write(folder / controller_name, controller)
            files = [{"path": name, "source": str((HERE / name).relative_to(REPO)),
                      "content": (HERE / name).read_text()} for name in MODULES]
            for name, value, source in (("config.json", config, folder / "config.json"),
                    ("case-spec.json", spec, folder / "case-spec.json"),
                    ("controller.json", controller, folder / controller_name)):
                files.append({"path": name, "source": str(source.relative_to(REPO)),
                    "content": json.dumps(value, indent=2, sort_keys=True) + "\n"})
            files.append({"path": "tests/test_offline.py", "content": OFFLINE_TEST})
            construction = {"law_id": plan["law_id"], "cell_id": plan["cell_id"],
                "actor": plan["actor"], "case_id": cid, "entrypoint": "runner.py",
                "files": files, "recording_description": description,
                "measurement_plan": {"selected_requirement": plan["requirement_dispositions"][0]["requirement"],
                    "original_source": "source-reviewed vehicle weight, district, route, local time, written permit and operation",
                    "saved_method": "SHA-bound original 20 Hz operation with independently reviewed administrative context"},
                "mechanisms": ["reviewed original municipal/DPW packet before Native mutation",
                    "same-tick heavy-vehicle road-ID and four-camera Native capture"],
                "static_checks": ["exact case, 20 Hz, four cameras",
                    "reviewed original sources and selected comparison values before Native mutation"],
                "termination_rules": {"duration_s": 45,
                    "early_termination": "retain failed capture; do not publish as original complete operation"}}
            construction_name = "construction.json" if candidate == "primary" else "fallback1-construction.json"
            digest = write(folder / construction_name, construction)
            if candidate == "primary":
                entry = {"case_id": cid, "construction": str((folder / construction_name).relative_to(HERE)),
                    "construction_sha256": digest, "kind": "delivery",
                    "measurement_procedure": {"entrypoint": "analysis.py"},
                    "fixture_recipe": str((folder / "fixture-recipe.json").relative_to(REPO)),
                    "measurement_contract": str((folder / "measurement-contract.json").relative_to(HERE)),
                    "acquisition": {name: {"entrypoint": "analysis.py", "method": method,
                        "evidence": "channels/" + name + ".jsonl"} for name, _, method in channel_definitions},
                    "candidate_risk": {"status": "physical",
                        "reason": "Original heavy vehicle may miss reviewed segment completion or four-view pixels within 45 seconds"},
                    "candidates": [],
                    "native_handoff": {"python_env_var": "CARLA_PYTHON",
                        "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT",
                        "site_review_env_var": "C393410_NIGHT_REVIEW_PACKET"}}
            else:
                entry["candidates"].append({"id": "fallback1",
                    "construction": str((folder / construction_name).relative_to(HERE)),
                    "construction_sha256": digest,
                    "trigger": {"source": "original route and four-view pixel audit",
                        "metric": "segment completion or camera visibility",
                        "failure_condition": "primary missed source-reviewed street segment or actual pixels within 45 seconds"},
                    "changed_knobs": ["target speed 4.0 to 3.0 m/s on unchanged vehicle, street, time, permit and cameras"]})
        requirements = []
        methods = {0: ("weight", "measure_weight"), 1: ("operation", "measure_operation"),
            2: ("route", "measure_route"), 3: ("district", "measure_district"),
            4: ("time", "measure_time"), 5: ("application", "measure_application"),
            6: ("vehicle_scope", "measure_vehicle_scope"), 7: ("conditions", "measure_conditions")}
        for index, disposition in enumerate(plan["requirement_dispositions"]):
            if cid not in disposition["case_ids"]:
                continue
            output_key, method = methods[index]
            requirements.append({"disposition_index": index,
                "requirement": disposition["requirement"], "source": disposition["source"],
                "kind": "measured", "method": method, "output_key": output_key,
                "value_type": "object",
                "inputs": ["original-night-truck-observations.json", "original-night-truck-receipt.json",
                           "reviewed-night-truck.json"]})
        write(folder / "measurement-contract.json", {"format": "worker-measurement-contract",
            "case_id": cid, "requirements": requirements,
            "negative": {"remove": ["original-night-truck-observations.json"],
                "error_contains": "Missing required source: original-night-truck-observations.json"}})
        entries.append(entry)
    write(HERE / "execution-manifest.draft.json", {"format": "worker-execution-manifest",
        "assignment_id": HERE.name, "status": "reviewed_original_night_truck_packet_required_at_capture",
        "runtime_manifest_sha256": hashlib.sha256((REPO / "runtime/SOURCE-MANIFEST.json").read_bytes()).hexdigest(),
        "cases": entries})
    first = HERE / "cases/night_nonroute_no_permit"
    for name, source in (("construction.json", "construction.json"), ("config.json", "config.json"),
                         ("case-spec.json", "case-spec.json"), ("controller.json", "controller-primary.json")):
        (HERE / name).write_bytes((first / source).read_bytes())
    (HERE / "tests").mkdir(exist_ok=True)
    (HERE / "tests/test_offline.py").write_text(OFFLINE_TEST)
    print(len(entries), "primary and fallback source-gated constructions")
    return entries


if __name__ == "__main__":
    build()
