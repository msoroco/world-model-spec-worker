"""Bind railroad stop authority and highway geometry to reviewed source bytes."""
import hashlib
import json
from pathlib import Path

ROLES = ("required-stop", "rail-crossing", "right-edge",
         "lane-markings", "right-availability", "gate-indication")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reviewed_context(folder):
    folder = Path(folder)
    provenance = json.loads((folder / "acquisition-provenance.json").read_text())
    diagnostic = provenance.get("provenance_kind") == "synthetic_fixture"
    if not diagnostic and provenance.get("provenance_kind") != "native_capture":
        raise ValueError("Original Native source provenance missing")
    sources = json.loads((folder / "sources.json").read_text())
    if sources.get("kind") != ("synthetic_cpu_rail_stop_queue" if diagnostic else "native_rail_stop_queue"):
        raise ValueError("Rail source kind differs from provenance")
    road = folder / "road.xodr"
    if not road.is_file():
        raise ValueError("Original road source missing")
    road_sha = sha(road)
    inventory = json.loads((folder / "rail-inventory.json").read_text())
    if inventory.get("road_sha256") != road_sha:
        raise ValueError("Rail inventory does not bind Native road")
    records = {}
    for role in ROLES:
        path = folder / "rail-review" / (role + ".json")
        source = folder / "rail-review" / (role + ".source.txt")
        if not path.is_file() or not source.is_file():
            raise ValueError("Missing required rail source: " + role)
        record = json.loads(path.read_text())
        if (record.get("role") != role or record.get("road_sha256") != road_sha
                or record.get("source_sha256") != sha(source)):
            raise ValueError("Reviewed rail source hash differs: " + role)
        if diagnostic:
            if record.get("provenance_kind") != "synthetic_fixture":
                raise ValueError("Diagnostic rail source provenance differs")
        elif (record.get("review_status") != "independently_reviewed"
              or not record.get("reviewer_id")
              or record.get("provenance_kind") != "original_native"
              or record.get("source_kind") in ("synthetic", "authored_assertion")):
            raise ValueError("Original independent rail source review required: " + role)
        records[role] = record
    required = records["required-stop"]
    if required.get("stop_required") is not True or not required.get("authority_clause"):
        raise ValueError("Required-stop authority not independently sourced")
    gate = records["gate-indication"]
    if gate.get("native_actor_id") != inventory.get("gate_actor_id"):
        raise ValueError("Reviewed gate does not bind Native actor")
    crossing = records["rail-crossing"]
    if crossing.get("crossing_x_m") != inventory.get("crossing_x_m"):
        raise ValueError("Rail crossing reference differs")
    edge = records["right-edge"]
    if edge.get("right_highway_edge_y_m") != inventory.get("right_highway_edge_y_m"):
        raise ValueError("Right highway edge source differs")
    markings = records["lane-markings"]
    if markings.get("total_marked_lanes") != inventory.get("total_marked_lanes"):
        raise ValueError("Marked lane count source differs")
    if records["right-availability"].get("right_space_reviewed") is not True:
        raise ValueError("Available right-side space source missing")
    return {"diagnostic_fixture": diagnostic, "road_sha256": road_sha,
            "reviewed_role_sha256": {role: sha(folder / "rail-review" / (role + ".json"))
                                    for role in ROLES},
            "gate_actor_id": gate["native_actor_id"],
            "total_marked_lanes": markings["total_marked_lanes"],
            "right_highway_edge_y_m": edge["right_highway_edge_y_m"],
            "legal_verdict_claimed": False}
