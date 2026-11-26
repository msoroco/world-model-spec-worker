"""Controlled lamp and motion requests for one source-reviewed motorcycle case.

The adapter must read back actual actor state and original camera frames. Requests
are never substituted for observations or calibrated lamp capability.
"""

import json
from pathlib import Path

from source_packet import ASSIGNMENT, verify as verify_source


LAMP_STATES = {
    "both_lit": (True, True),
    "head_off": (False, True),
    "tail_off": (True, False),
    "both_off": (False, False),
}


def prepare(adapter, packet_path, case_plan_path, *, diagnostic_fixture=False):
    verified = verify_source(packet_path, diagnostic_fixture=diagnostic_fixture)
    plan = json.loads(Path(case_plan_path).read_text(encoding="utf-8"))
    exact = next((case for case in plan["cases"] if case["case_id"] == verified["case_id"]), None)
    if exact is None or plan["assignment_id"] != ASSIGNMENT:
        raise ValueError("exact source packet case not in selected plan")
    scene = json.loads(Path(packet_path).read_text(encoding="utf-8"))["scene"]
    for name in ("coverage_request", "illumination_request", "motion_request",
                 "calibrated_lamp_request", "lit_state_request", "timing_request",
                 "discernibility_request_ft"):
        if scene[name] != exact[name]:
            raise ValueError("controlled case request differs: " + name)
    if not callable(getattr(adapter, "loaded_map_bytes", None)):
        raise ValueError("original Native map readback required")
    if verified["source_hashes"]["map_opendrive"] != adapter.sha_bytes(adapter.loaded_map_bytes()):
        raise ValueError("loaded Native map differs from reviewed OpenDRIVE")
    if not callable(getattr(adapter, "verify_sidewalk", None)) or not adapter.verify_sidewalk(
            scene["route"], scene["sidewalk"]):
        raise ValueError("roadway and separate physical sidewalk readback failed")
    if not callable(getattr(adapter, "spawn_vehicle", None)):
        raise ValueError("Native motorcycle spawn required")
    ego = adapter.spawn_vehicle(scene["vehicle_blueprint"], scene["route"])
    if not callable(getattr(adapter, "vehicle_blueprint_id", None)) or \
            adapter.vehicle_blueprint_id(ego) != scene["vehicle_blueprint"]:
        raise ValueError("spawned motorcycle blueprint differs")
    head, tail = LAMP_STATES[scene["lit_state_request"]]
    if not callable(getattr(adapter, "set_lamps", None)) or not adapter.set_lamps(ego, head, tail):
        raise ValueError("independent head and tail lamp control not applied")
    if not callable(getattr(adapter, "read_lamps", None)) or adapter.read_lamps(ego) != (head, tail):
        raise ValueError("independent head and tail lamp readback failed")
    if not callable(getattr(adapter, "set_weather", None)) or not adapter.set_weather(scene):
        raise ValueError("original weather and sun setup failed")
    if not callable(getattr(adapter, "read_weather", None)) or not adapter.read_weather(scene):
        raise ValueError("original weather and sun readback failed")
    if not callable(getattr(adapter, "set_route", None)) or not adapter.set_route(
            ego, scene["route"], scene["requested_speed_mps"]):
        raise ValueError("source-grounded roadway route control failed")
    return {"case_id": exact["case_id"], "ego": ego,
            "source_packet_sha256": verified["packet_sha256"],
            "requested_lamps": {"head": head, "tail": tail},
            "observed_lamps_initial": {"head": head, "tail": tail},
            "physical_completion": "unverified"}
