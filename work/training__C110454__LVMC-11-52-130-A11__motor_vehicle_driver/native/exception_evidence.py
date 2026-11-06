"""Source-bound exception evidence gates; no legal exception verdict."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

NEEDED={
    "necessary_traffic_conflict": ("other_actor_frames","ego_brake_frames","intersection_boundary_source"),
    "compliance_with_law": ("cited_law_id","cited_law_text_sha256","ego_action_frames"),
    "police_or_device_direction": ("original_pixel_sha256","direction_source_id","direction_frame","ego_action_frames"),
}


def inspect(source:Path,expected_sha256:str,branch:str)->dict:
    if branch not in NEEDED:raise ValueError("Unknown statutory exception")
    if hashlib.sha256(source.read_bytes()).hexdigest()!=expected_sha256:
        raise ValueError("Exception evidence source hash differs")
    packet=json.loads(source.read_text())
    if packet.get("source_kind")!="native_context_schema" or packet.get("branch")!=branch:
        raise ValueError("Exception evidence identity differs")
    missing=[key for key in NEEDED[branch] if not packet.get(key)]
    if missing:raise ValueError("Missing original exception source: "+missing[0])
    if branch=="necessary_traffic_conflict":
        actors=packet["other_actor_frames"];brakes=packet["ego_brake_frames"]
        if (not isinstance(actors,list) or not isinstance(brakes,list) or
            any(type(i)!=int or i<0 or i>=480 for i in actors+brakes) or
            not set(actors)&set(brakes)):
            raise ValueError("Conflict and ego response are not time joined")
    elif branch=="compliance_with_law":
        if (len(packet["cited_law_text_sha256"])!=64 or
            not isinstance(packet["ego_action_frames"],list)):
            raise ValueError("Cited law or observed action source differs")
    else:
        if (len(packet["original_pixel_sha256"])!=64 or
            type(packet["direction_frame"])!=int or
            packet["direction_frame"] not in packet["ego_action_frames"]):
            raise ValueError("Direction pixels and actor action are not joined")
    return {"branch":branch,"source_sha256":expected_sha256,
            "source_packet_complete":True,"applicability":"requires_independent_review",
            "physical_observation_claimed":False,"legal_exception_verdict":None}
