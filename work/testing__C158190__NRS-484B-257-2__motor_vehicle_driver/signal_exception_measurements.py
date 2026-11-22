"""Original-frame signal exception and occupied-intersection observations.

The source context must establish a non-through-highway signed entrance and
every competing entrance's device. No legal hazard or caution verdict is made.
"""

import hashlib
import json
import math
from pathlib import Path


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite " + label)
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _ego_body(row):
    body = row.get('ego', {}).get('body_vertices_m')
    if not isinstance(body, list) or len(body) < 8:
        raise ValueError('Missing original ego body vertices')
    for point in body:
        if not isinstance(point, list) or len(point) != 3:
            raise ValueError('Incomplete original ego body vertex')
        for value in point:
            _finite(value, 'ego body vertex')
    return body


def measure_signed_entrance(context, observations):
    return {'native_stop_sign_id': context['native_stop_sign_id'],
            'non_through_highway': context['non_through_highway'],
            'entrances': context['entrances']}


def measure_full_stop_before_entry(context, observations):
    return observations['observed_full_stop_before_reference']


def measure_other_intersection_occupancy(context, observations):
    return observations['observed_other_occupancy']


def measure_control_exception(context, observations):
    return {'police_control': context['police_control'],
            'traffic_signal_control': context['traffic_signal_control'],
            'native_signal_id': context['native_signal_id'],
            'signal_states': observations['governing_signal_states']}


def measure_approaching_hazard_context(context, observations):
    return {'other_approach_samples': [
                {'frame': row['frame'], 'time_s': row['time_s'],
                 'other_center_m': row['other_center_m'],
                 'other_speed_mps': row['other_speed_mps'],
                 'other_body_in_intersection': row['other_body_in_intersection']}
                for row in observations['samples'] if row['other_center_m'] is not None],
            'first_ego_entry_frame': observations['first_ego_entry_frame'],
            'legal_hazard_judgment': 'unresolved'}


REVIEW_SOURCES = ("intersection_context.json", "entry_history.jsonl",
                  "video_frames.jsonl", "stop_control_inventory.jsonl",
                  "signal_control_inventory.jsonl",
                  "overview.mkv", "approach.mkv", "reference_corner.mkv",
                  "driver_reference.mkv")


def _review_context(root, original, hashes):
    """Overlay explicit source review; retain the original capture unchanged."""
    path = root / "stop_context_review.json"
    if not path.is_file():
        raise ValueError("Missing hash-bound stop context review")
    review = json.loads(path.read_text())
    if review.get("format") != "worker-stop-context-review":
        raise ValueError("Wrong stop context review format")
    if not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip():
        raise ValueError("Missing independent stop context reviewer")
    if not isinstance(review.get("method"), str) or not review["method"].strip():
        raise ValueError("Missing original-source review method")
    expected = {}
    for name in REVIEW_SOURCES:
        source = root / name
        if not source.is_file():
            raise ValueError("Missing reviewed original source: " + name)
        expected[name] = hashlib.sha256(source.read_bytes()).hexdigest()
    if review.get("source_hashes") != expected:
        raise ValueError("Stale or incomplete stop context source hashes")
    findings = review.get("findings")
    if not isinstance(findings, dict):
        raise ValueError("Missing stop context findings")
    if findings.get("native_map_id") != original.get("native_map_id") or \
       findings.get("native_stop_sign_id") != original.get("native_stop_sign_id") or \
       findings.get("native_signal_id") != original.get("native_signal_id"):
        raise ValueError("Reviewed Native map/sign identity differs")
    if findings.get("stop_sign_face_legible") is not True:
        raise ValueError("Stop sign face not independently visible")
    if findings.get("stop_reference_kind") not in ("stop_line", "crosswalk", "nearest_view"):
        raise ValueError("Stop-reference hierarchy remains unresolved")
    if not isinstance(findings.get("stop_reference_source"), str) or \
       not findings["stop_reference_source"].strip():
        raise ValueError("Missing sourced stop reference")
    for key in ("non_through_highway", "police_control", "traffic_signal_control"):
        if type(findings.get(key)) is not bool:
            raise ValueError("Missing reviewed control/highway status: " + key)
    entrances = findings.get("entrances")
    if not isinstance(entrances, list) or len(entrances) < 2 or any(
            type(e.get("road_id")) is not int or
            e.get("device") not in ("stop", "yield", "signal", "stop_and_signal", "none")
            for e in entrances if isinstance(e, dict)) or any(
            not isinstance(e, dict) for e in entrances):
        raise ValueError("Incomplete reviewed entrance inventory")
    if {e["road_id"] for e in entrances} != {e["road_id"] for e in original["entrances"]}:
        raise ValueError("Reviewed entrance IDs differ from Native plan")
    if len({e["road_id"] for e in entrances}) != len(entrances):
        raise ValueError("Duplicate reviewed entrance identity")
    merged = dict(original)
    merged.update({key: findings[key] for key in
                   ("non_through_highway", "police_control", "traffic_signal_control",
                    "entrances", "stop_reference_source", "native_signal_id")})
    merged["entrance_inventory_source"] = "hash_bound_original_camera_and_control_review"
    merged["highway_status_source"] = "hash_bound_original_map_and_camera_review"
    hashes.update(expected)
    hashes["stop_context_review.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return merged


def analyze(root: Path):
    root = Path(root)
    names = ("intersection_context.json", "entry_history.jsonl", "video_frames.jsonl")
    hashes = {}
    for name in names:
        path = root/name
        if not path.is_file():
            raise ValueError("Missing original source: " + name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = json.loads((root/"intersection_context.json").read_text())
    if any(context.get(key) is None for key in
           ("non_through_highway", "police_control", "traffic_signal_control")) or \
       any(e.get("device") == "unreviewed" for e in context.get("entrances", [])
           if isinstance(e, dict)):
        context = _review_context(root, context, hashes)
    for key in ("native_map_id", "intersection_id", "ego_approach_road_id",
                "native_stop_sign_id", "native_signal_id", "sign_governance_source", "entrance_inventory_source",
                "stop_reference_source", "highway_status_source"):
        if context.get(key) is None:
            raise ValueError("Missing sourced intersection context: " + key)
    if context.get("non_through_highway") is not True:
        raise ValueError("Non-through-highway status not sourced")
    if context.get("police_control") is not False or context.get("traffic_signal_control") is not True:
        raise ValueError("Governing signal exception unresolved")
    if context.get("ego_entrance_device") != "stop":
        raise ValueError("Ego stop-sign governance missing")
    entrances = context.get("entrances")
    if not isinstance(entrances, list) or len(entrances) < 2 or any("road_id" not in e or "device" not in e for e in entrances):
        raise ValueError("Incomplete entrance device inventory")
    rows, frames = _rows(root/"entry_history.jsonl"), _rows(root/"video_frames.jsonl")
    signals = _rows(root/"signal_control_inventory.jsonl")
    hashes["signal_control_inventory.jsonl"] = hashlib.sha256(
        (root/"signal_control_inventory.jsonl").read_bytes()).hexdigest()
    if len(rows) < 3 or len(rows) != len(frames) or len(rows) != len(signals):
        raise ValueError("Incomplete entry history")
    samples, previous = [], (-1, -math.inf)
    for index, (row, frame) in enumerate(zip(rows, frames)):
        fid, time = row.get("frame"), _finite(row.get("time_s"), "time")
        if type(fid) is not int or fid <= previous[0] or time <= previous[1]:
            raise ValueError("Nonmonotone original history")
        previous = fid, time
        if frame.get("video_frame") != index or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original frame join failed")
        signal_row = signals[index]
        if (signal_row.get("frame") != fid or
                signal_row.get("native_signal_id") != context["native_signal_id"] or
                signal_row.get("affected_ego_road_id") != context["ego_approach_road_id"] or
                signal_row.get("affected_ego_lane_id") != -1 or
                signal_row.get("state") not in ("Green", "TrafficLightState.Green") or
                signal_row.get("source") != "Native light actor, affected lane and frame join" or
                not isinstance(signal_row.get("trigger_vertices_m"), list) or
                len(signal_row["trigger_vertices_m"]) < 4):
            raise ValueError("Original governing signal frame or lane differs")
        for vertex in signal_row["trigger_vertices_m"]:
            if not isinstance(vertex, list) or len(vertex) != 3:
                raise ValueError("Original signal trigger vertex incomplete")
            for coordinate in vertex:
                _finite(coordinate, "signal trigger coordinate")
        road_id = row.get("ego_road_id")
        if index == 0 and road_id != context["ego_approach_road_id"]:
            raise ValueError("Ego approach identity mismatch")
        allowed_route = context.get("ego_route_road_ids", [context["ego_approach_road_id"]])
        if road_id not in allowed_route:
            raise ValueError("Ego route identity mismatch")
        if row.get("ego_speed_source") != "actor.get_velocity":
            raise ValueError("Ego Native velocity source missing")
        speed = _finite(row.get("ego_speed_mps"), "ego speed")
        if speed < 0:
            raise ValueError("Negative ego speed")
        entry, before_ref = row.get("ego_body_in_intersection"), row.get("ego_body_before_stop_reference")
        other_in = row.get("other_body_in_intersection")
        if any(type(v) is not bool for v in (entry, before_ref, other_in)):
            raise ValueError("Missing original body occupancy")
        body = _ego_body(row)
        computed_entry = (min(p[0] for p in body) <= 8 and max(p[0] for p in body) >= -8
                          and min(p[1] for p in body) <= 8 and max(p[1] for p in body) >= -8)
        computed_before = max(p[0] for p in body) < -11
        if (entry, before_ref) != (computed_entry, computed_before):
            raise ValueError('Original ego body disagrees with sampled occupancy or stop reference')
        other_center, other_speed = row.get('other_center_m'), row.get('other_speed_mps')
        if other_center is not None:
            if (not isinstance(other_center, list) or len(other_center) != 3
                    or other_speed is None):
                raise ValueError('Incomplete other approach source sample')
            other_center = [_finite(v, 'other center') for v in other_center]
            other_speed = _finite(other_speed, 'other speed')
            if other_speed < 0:
                raise ValueError('Negative other speed')
        elif other_speed is not None:
            raise ValueError('Other speed without source position')
        if other_in and other_center is None:
            raise ValueError('Occupied intersection lacks other source position')
        samples.append({"frame":fid,"time_s":time,"ego_speed_mps":speed,
                        "ego_body_in_intersection":entry,"ego_body_before_stop_reference":before_ref,
                        "other_body_in_intersection":other_in,
                        "other_center_m": other_center,
                        "other_speed_mps": other_speed,
                        "governing_signal_state": signal_row["state"]})
    first_entry = next((i for i,s in enumerate(samples) if s["ego_body_in_intersection"]), None)
    if first_entry is None or first_entry == 0:
        raise ValueError("No observed approach before entry")
    stopped = [s for s in samples[:first_entry] if s["ego_body_before_stop_reference"] and s["ego_speed_mps"] == 0]
    other_occupied = [s for s in samples if s["other_body_in_intersection"]]
    return {"format":"worker-signal-exception-intersection-observations","sources":hashes,
            "first_ego_entry_frame":samples[first_entry]["frame"],
            "observed_full_stop_before_reference":bool(stopped),
            "observed_other_occupancy":bool(other_occupied),"samples":samples,
            "native_signal_id":context["native_signal_id"],
            "governing_signal_states":[{"frame":r["frame"],"state":r["governing_signal_state"]}
                                       for r in samples],
            "immediate_hazard_judgment":"unresolved; no legal time-to-conflict cutoff",
            "caution_and_yield_judgment":"unresolved","legal_conclusion":"unresolved"}


def finalize(attempt: Path, output: Path):
    """Write saved observations from immutable capture and separate review sources."""
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists() or (attempt / "channels").exists():
        raise ValueError("Retain prior stop-sign finalization; use a fresh attempt")
    required = ("config.json", "trace.jsonl", "capture/evidence.jsonl",
                "capture/native_map_facts.json", *REVIEW_SOURCES,
                "stop_context_review.json")
    for name in required:
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    case_id = config.get("selected_case_id", "")
    if not case_id.startswith(
            "testing__C158190__NRS-484B-257-2__motor_vehicle_driver__"):
        raise ValueError("Wrong exact stop-sign case")
    if not case_id.endswith("signal_control_exception"):
        raise ValueError("Wrong exact signal-control exception case")
    report = analyze(attempt)
    frame_map = _rows(attempt / "video_frames.jsonl")
    if len(frame_map) != len(report["samples"]):
        raise ValueError("Saved stop history and original footage differ")
    observed_stop = report["observed_full_stop_before_reference"]
    target = {"target": "governing_signal_green_during_sampled_entry",
              "requested": True, "measured": all(
                  row["state"] in ("Green", "TrafficLightState.Green")
                  for row in report["governing_signal_states"]),
              "method": "original Native affected-lane signal state joined to video frames",
              "tolerance": 0, "matched": True,
              "physical_cause_confirmed": False,
              "cause_evidence": ["signal_control_inventory.jsonl", "video_frames.jsonl",
                                 "stop_context_review.json"]}
    values = {
        "governing_signal_state": [
            {"original_frame": row["frame"], "time_s": row["time_s"],
             "value": {"native_signal_id": report["native_signal_id"],
                       "state": row["governing_signal_state"]}}
            for row in report["samples"]],
        "ego_speed_and_stop_reference": [
            {"original_frame": row["frame"], "time_s": row["time_s"],
             "value": {"ego_speed_mps": row["ego_speed_mps"],
                       "body_before_stop_reference": row["ego_body_before_stop_reference"]}}
            for row in report["samples"]],
        "ego_and_other_intersection_occupancy": [
            {"original_frame": row["frame"], "time_s": row["time_s"],
             "value": {"ego_body_in_intersection": row["ego_body_in_intersection"],
                       "other_body_in_intersection": row["other_body_in_intersection"]}}
            for row in report["samples"]],
        "other_approach_history": [
            {"original_frame": row["frame"], "time_s": row["time_s"],
             "value": {"other_actor_id": source.get("other_actor_id"),
                       "other_speed_mps": source.get("other_speed_mps"),
                       "other_center_m": source.get("other_center_m")}}
            for row, source in zip(report["samples"], _rows(attempt / "entry_history.jsonl"))],
    }
    units = {"ego_speed_and_stop_reference": "m/s and m",
             "ego_and_other_intersection_occupancy": "structured record",
             "other_approach_history": "structured record",
             "governing_signal_state": "structured record"}
    evidence = [{"name": name, "unit": units[name],
                 "reference": "channels/" + name + ".jsonl"} for name in values]
    evidence.append({"name": "stop_control_and_entrance_review",
                     "unit": "structured record",
                     "reference": "channels/stop_control_and_entrance_review.json"})
    hashes = dict(report["sources"])
    for name in ("config.json", "trace.jsonl", "capture/evidence.jsonl",
                 "capture/native_map_facts.json"):
        hashes[name] = hashlib.sha256((attempt / name).read_bytes()).hexdigest()
    measurement_specs = (
        ('signed_entrance_control', measure_signed_entrance,
         ('intersection_context.json', 'stop_control_inventory.jsonl',
          'signal_control_inventory.jsonl')),
        ('full_stop_before_entry', measure_full_stop_before_entry,
         ('intersection_context.json', 'entry_history.jsonl', 'video_frames.jsonl')),
        ('other_intersection_occupancy', measure_other_intersection_occupancy,
         ('entry_history.jsonl', 'video_frames.jsonl')),
        ('control_exception_state', measure_control_exception,
         ('intersection_context.json', 'stop_control_inventory.jsonl',
          'signal_control_inventory.jsonl')),
        ('approaching_hazard_context', measure_approaching_hazard_context,
         ('entry_history.jsonl', 'video_frames.jsonl')),
    )
    for name in ('stop_control_inventory.jsonl', 'signal_control_inventory.jsonl'):
        hashes[name] = hashlib.sha256((attempt / name).read_bytes()).hexdigest()
    context = json.loads((attempt / 'intersection_context.json').read_text())
    if any(context.get(key) is None for key in
           ('non_through_highway', 'police_control', 'traffic_signal_control')):
        context = _review_context(attempt, context, {})
    measurements = {
        key: {'method': method.__name__, 'value': method(context, report),
              'sources': {name: hashes[name] for name in inputs}}
        for key, method, inputs in measurement_specs
    }
    result = {"case_id": case_id,
              "measured_values": {
                  "observed_full_stop_before_reference": observed_stop,
                  "governing_signal_green_all_frames": target["measured"],
                  "first_ego_entry_frame": report["first_ego_entry_frame"],
                  "observed_other_occupancy": report["observed_other_occupancy"]},
              "target_checks": [target], "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "saved-source analysis; physical review pending",
              "physical_failure_flags": [
                  "sign face, highway classification, immediate hazard and yielding need original-source review"],
              "trace_reference": "trace.jsonl",
              "video_references": ["overview.mkv", "approach.mkv",
                                   "reference_corner.mkv", "driver_reference.mkv"],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["recording_description"],
              "recording_evidence": evidence,
              "source_evidence_hashes": hashes,
              "capture_evidence_sha256": hashes["capture/evidence.jsonl"],
              "realized_observables": {}}
    from worker_exchange.native_output import physical_result, write_result
    result = physical_result(attempt, result)
    channels = attempt / "channels"
    channels.mkdir()
    for name, samples in values.items():
        with (channels / (name + ".jsonl")).open("x") as stream:
            for sample in samples:
                stream.write(json.dumps(sample, allow_nan=False) + "\n")
    review = json.loads((attempt / "stop_context_review.json").read_text())
    (channels / "stop_control_and_entrance_review.json").write_text(
        json.dumps({"stop_control_and_entrance_review": review}, allow_nan=False) + "\n")
    write_result(attempt, result)
    analysis = {"format": "worker-signal-exception-saved-analysis", "case_id": case_id,
                "observations": report, "source_evidence_hashes": hashes,
                "measurements": measurements,
                "physical_checks": result["physical_checks"],
                "legal_conclusion": "unresolved"}
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + "\n")
    return analysis


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)


if __name__ == "__main__":
    main()
