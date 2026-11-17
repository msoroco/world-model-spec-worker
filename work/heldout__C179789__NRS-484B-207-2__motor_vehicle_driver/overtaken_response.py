"""Measure an overtaken driver's response from retained original CPU sources.

The result contains observations and source hashes, never a legal verdict.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _source(path):
    data = Path(path).read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()


def measure(context_path, events_path, motion_path):
    context, context_hash = _source(context_path)
    events, events_hash = _source(events_path)
    motion, motion_hash = _source(motion_path)
    subject = context.get("subject_id")
    overtaker = context.get("overtaker_id")
    if not subject or not overtaker or subject == overtaker:
        raise ValueError("Original participant identities differ or are missing")
    if not context.get("road_source") or not context.get("actor_source"):
        raise ValueError("Original road and actor sources are required")
    if not isinstance(context.get("right_pass_permitted"), bool) or not context.get("right_pass_permission_source"):
        raise ValueError("Right-pass exception needs a sourced premise")
    if events.get("subject_id") != subject or events.get("overtaker_id") != overtaker:
        raise ValueError("Original event identities differ")
    if events.get("notice_kind") not in ("observed_vehicle", "audible_signal") or not events.get("notice_source"):
        raise ValueError("Observed or audible notice source is required")
    notice = events.get("notice_frame")
    complete = events.get("pass_complete_frame")
    if not isinstance(notice, int) or not isinstance(complete, int) or complete <= notice:
        raise ValueError("Pass completion must follow notice in original frame order")
    frames = motion.get("frames", [])
    if not isinstance(frames, list):
        raise ValueError("Original motion frames must be a list")
    by_frame = {}
    for row in frames:
        if row.get("subject_id") != subject or row.get("overtaker_id") != overtaker:
            raise ValueError("Original motion identities differ")
        frame = row.get("frame")
        if not isinstance(frame, int) or frame in by_frame:
            raise ValueError("Original motion frame IDs must be unique integers")
        for key in ("speed_mps", "right_offset_m"):
            if isinstance(row.get(key), bool) or not isinstance(row.get(key), (int, float)):
                raise ValueError("Original motion needs numeric "+key)
        by_frame[frame] = row
    baseline = by_frame.get(notice)
    precompletion = [by_frame[f] for f in sorted(by_frame) if notice < f < complete]
    if baseline is None or not precompletion:
        raise ValueError("There are no motion samples after notice and before pass completion")
    return {
        "subject_id": subject,
        "overtaker_id": overtaker,
        "notice_kind": events["notice_kind"],
        "notice_frame": notice,
        "pass_complete_frame": complete,
        "right_pass_permitted_premise": context["right_pass_permitted"],
        "right_pass_permission_source": context["right_pass_permission_source"],
        "road_source": context["road_source"],
        "actor_source": context["actor_source"],
        "notice_source": events["notice_source"],
        "source_sha256": {"context": context_hash, "events": events_hash, "motion": motion_hash},
        "source_paths": {"context": str(Path(context_path).resolve()),
                         "events": str(Path(events_path).resolve()),
                         "motion": str(Path(motion_path).resolve())},
        "max_right_shift_m": max(row["right_offset_m"] - baseline["right_offset_m"] for row in precompletion),
        "max_precompletion_speed_delta_mps": max(row["speed_mps"] - baseline["speed_mps"] for row in precompletion),
        "legal_conclusion": None,
    }


def verify_saved_sources(source_path, frame_map_path, trace_path):
    """Recompute body completion and lateral offset across original frame joins.

    A construction stimulus is retained as a fact about the test script, never
    promoted into evidence of the driver seeing or hearing the overtaker.
    """
    paths = [Path(source_path), Path(frame_map_path), Path(trace_path)]
    for path in paths:
        if not path.is_file() or not path.read_bytes():
            raise ValueError("Missing required source: " + path.name)
    blobs = [path.read_bytes() for path in paths]
    rows = [[json.loads(line) for line in blob.splitlines() if line.strip()] for blob in blobs]
    source, mapping, trace = rows
    if not source or len(source) != len(mapping) or len(source) != len(trace):
        raise ValueError("Original source/frame-map lengths differ")

    def number(value):
        return type(value) in (int, float) and math.isfinite(value)

    def point(value):
        if not isinstance(value, list) or len(value) != 2 or not all(number(v) for v in value):
            raise ValueError("Original body/road point invalid")
        return value

    first_ids = source[0].get("subject_id"), source[0].get("overtaker_id")
    if not all(first_ids) or first_ids[0] == first_ids[1]:
        raise ValueError("Original participant identities differ")
    verified = []
    for index, (body, frame_map, motion) in enumerate(zip(source, mapping, trace)):
        frame, time_s = body.get("frame"), body.get("time_s")
        if type(frame) is not int or not number(time_s) or (
            index and (frame != source[index-1]["frame"] + 1 or
                       abs(time_s - source[index-1]["time_s"] - .05) > 1e-4)
        ):
            raise ValueError("Original source is not contiguous at 20 Hz")
        if (body.get("subject_id"), body.get("overtaker_id")) != first_ids:
            raise ValueError("Original participant identities differ")
        if (frame_map.get("video_frame") != index or
            frame_map.get("carla_frame") != frame or
            frame_map.get("time_s") != time_s or
            motion.get("frame") != frame or motion.get("time_s") != time_s):
            raise ValueError("Original source/frame-map join failed")
        tangent = point(body.get("road_tangent_xy"))
        waypoint = point(body.get("road_waypoint_xy"))
        pose = point(body.get("subject_pose_xy"))
        if abs(math.hypot(*tangent)-1) > .01:
            raise ValueError("Original road tangent invalid")
        corners = []
        for key in ("subject_corners", "overtaker_corners"):
            shape = body.get(key)
            if not isinstance(shape, list) or len(shape) != 4:
                raise ValueError("Original body corners missing")
            corners.append([point(vertex) for vertex in shape])
        subject_long = [x*tangent[0]+y*tangent[1] for x,y in corners[0]]
        overtaker_long = [x*tangent[0]+y*tangent[1] for x,y in corners[1]]
        complete = min(overtaker_long) > max(subject_long)
        offset = (pose[0]-waypoint[0])*tangent[1] - (pose[1]-waypoint[1])*tangent[0]
        if type(body.get("body_pass_complete")) is not bool or body["body_pass_complete"] != complete:
            raise ValueError("Original body pass-completion readback differs")
        if not number(body.get("subject_right_offset_m")) or abs(body["subject_right_offset_m"]-offset) > 1e-6:
            raise ValueError("Original right-offset readback differs")
        if (not number(body.get("subject_speed_mps")) or
            not number(motion.get("speed_mps")) or
            abs(body["subject_speed_mps"]-motion["speed_mps"]) > 1e-5):
            raise ValueError("Original speed/trace readback differs")
        if (type(body.get("notice_stimulus")) is not bool or
            type(body.get("notice_observed")) not in (bool, type(None))):
            raise ValueError("Original notice fields invalid")
        relation = body.get("visibility_relation")
        if relation is None:
            if body["notice_observed"] is not None:
                raise ValueError("Original notice lacks visibility rays")
        else:
            rays = relation.get("rays") if isinstance(relation, dict) else None
            if (str(relation.get("a")) != first_ids[0] or
                str(relation.get("b")) != first_ids[1] or
                not isinstance(rays, list) or not rays or
                any(type(ray.get("clear")) is not bool or
                    not isinstance(ray.get("blockers"), list) or
                    ray["clear"] != (not ray["blockers"]) for ray in rays) or
                type(relation.get("visible")) is not bool or
                relation["visible"] != any(ray["clear"] for ray in rays) or
                body["notice_observed"] != relation["visible"]):
                raise ValueError("Original notice visibility rays differ")
        if type(body.get("right_pass_permission_verified")) not in (bool, type(None)):
            raise ValueError("Original right-pass permission field invalid")
        verified.append({"frame":frame,"time_s":time_s,"subject_id":first_ids[0],
                         "overtaker_id":first_ids[1],"speed_mps":motion["speed_mps"],
                         "right_offset_m":offset,"body_pass_complete":complete,
                         "notice_stimulus":body["notice_stimulus"],
                         "notice_observed":body["notice_observed"],
                         "right_pass_permission_verified":body["right_pass_permission_verified"]})
    return {"format":"worker-overtaken-saved-source-verification",
            "source_sha256":{path.name:hashlib.sha256(blob).hexdigest()
                             for path,blob in zip(paths,blobs)},
            "frames":verified,"legal_conclusion":None}


def measure_observed_saved(source_path, frame_map_path, trace_path):
    """Measure the observed-vehicle branch from verified original body/ray sources."""
    verified = verify_saved_sources(source_path, frame_map_path, trace_path)
    frames = verified["frames"]
    notices = [row for row in frames if row["notice_observed"] is True]
    if not notices:
        raise ValueError("No original subject-to-overtaker visibility notice")
    notice = notices[0]
    completed = [row for row in frames if row["body_pass_complete"] and
                 row["frame"] > notice["frame"]]
    if not completed:
        raise ValueError("No original body pass completion after notice")
    complete = completed[0]
    interval = [row for row in frames if notice["frame"] < row["frame"] < complete["frame"]]
    if not interval:
        raise ValueError("No precompletion motion after original notice")
    return {"notice_kind":"observed_vehicle",
            "notice_method":"original subject-to-overtaker body collision rays",
            "notice_frame":notice["frame"],
            "pass_complete_frame":complete["frame"],
            "max_right_shift_m":max(row["right_offset_m"]-notice["right_offset_m"]
                                    for row in interval),
            "max_precompletion_speed_delta_mps":max(row["speed_mps"]-notice["speed_mps"]
                                                     for row in interval),
            "source_sha256":verified["source_sha256"],
            "source_paths":{path.name:str(path.resolve()) for path in
                            (Path(source_path),Path(frame_map_path),Path(trace_path))},
            "legal_conclusion":None,
            "limitations":["Collision rays establish simulated line of sight, not actual human observation or legal compliance."]}


def measure_audible_saved(source_path, frame_map_path, trace_path,
                          command_path, envelope_path):
    """Join generated signal records to original motion without inferring hearing."""
    verified = verify_saved_sources(source_path, frame_map_path, trace_path)
    frames = verified["frames"]
    paths = (Path(command_path), Path(envelope_path))
    signals = []
    hashes = dict(verified["source_sha256"])
    for path in paths:
        if not path.is_file() or not path.read_bytes():
            raise ValueError("Missing original generated signal source: " + path.name)
        blob = path.read_bytes()
        signals.append([json.loads(line) for line in blob.splitlines() if line.strip()])
        hashes[path.name] = hashlib.sha256(blob).hexdigest()
    commands, envelope = signals
    if len(commands) != len(frames) or len(envelope) != len(frames):
        raise ValueError("Original generated signal/frame lengths differ")
    notices = []
    for frame, command, audio in zip(frames, commands, envelope):
        common = (frame["frame"], frame["time_s"], str(frame["overtaker_id"]))
        if ((command.get("frame"), command.get("time_s"),
             command.get("overtaker_actor_id")) != common or
            (audio.get("frame"), audio.get("time_s"),
             audio.get("overtaker_actor_id")) != common or
            command.get("source_kind") != "scenario_signal_command" or
            audio.get("source_kind") != "generated_signal_envelope" or
            type(command.get("horn_command_requested")) is not bool or
            frame["notice_stimulus"] != command["horn_command_requested"] or
            audio.get("generated_rms") !=
                (0.6 if command["horn_command_requested"] else 0.0) or
            audio.get("acoustic_propagation_confirmed") is not None or
            audio.get("subjective_hearing_confirmed") is not None):
            raise ValueError("Original generated signal/frame join differs")
        if command["horn_command_requested"]:
            notices.append(frame)
    if not notices:
        raise ValueError("No original generated signal command")
    notice = notices[0]
    completed = [row for row in frames if row["body_pass_complete"] and
                 row["frame"] > notice["frame"]]
    if not completed:
        raise ValueError("No original body pass completion after signal command")
    complete = completed[0]
    interval = [row for row in frames if notice["frame"] < row["frame"] < complete["frame"]]
    if not interval:
        raise ValueError("No precompletion motion after signal command")
    return {"notice_kind":"audible_signal_command", "notice_frame":notice["frame"],
            "pass_complete_frame":complete["frame"],
            "max_right_shift_m":max(row["right_offset_m"]-notice["right_offset_m"]
                                    for row in interval),
            "max_precompletion_speed_delta_mps":max(row["speed_mps"]-notice["speed_mps"]
                                                     for row in interval),
            "source_sha256":hashes, "hearing_confirmed":None,
            "acoustic_propagation_confirmed":None, "legal_conclusion":None,
            "limitations":["Generated command and envelope establish the scripted signal source, not acoustic propagation or human hearing."]}
