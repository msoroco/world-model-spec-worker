"""Saved-only C104538 mounted-bicycle diagnostic; never a legal finding."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    if not path.is_file():
        raise ValueError("Missing required source: "+path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def video_frames(path):
    if not path.is_file():
        raise ValueError("Missing required source: "+path.name)
    result = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=nb_read_frames", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if result.returncode or not result.stdout.strip().isdigit():
        raise ValueError("Source camera decode failed: "+path.name)
    return int(result.stdout.strip())


def write_rows(path, values):
    path.parent.mkdir(exist_ok=True)
    path.write_text("".join(json.dumps(value, allow_nan=False)+"\n" for value in values))


def rebuild_channels(root, description, native, mapping, rider, trace, sign):
    """Derive diagnostic observations from retained rows, never fixture channels."""
    channels = root/"channels"
    if channels.exists():
        raise ValueError("Fixture-supplied derived channels are not accepted")
    channels.mkdir()
    for channel in description["channels"]:
        name = channel["name"]
        values = []
        for n, m, r, t in zip(native, mapping, rider, trace):
            if name == "ru.bicycle":
                value = {"actor_id": r["actor_id"], "blueprint": "vehicle.bh.crossbike", "body_xy_m": n["native_body_xy_m"]}
            elif name in ("ru.electric_bicycle", "ru.electric_scooter"):
                value = {"actor_id": r["actor_id"], "machine_class": r["machine_class"],
                         "selected_class": r["machine_class"] == name.split(".", 1)[1]}
            elif name == "ru.rider_posture":
                value = {"mounted_fixture": r["mounted"], "original_pixel_review": "pending"}
            elif name == "ru.pedestrian":
                value = {"walking_machine_fixture": r["walking_machine"],
                         "original_pixel_review": "pending"}
            elif name == "dev.regulatory_sign":
                value = {"code": sign["code"], "authorization_proven": False}
            elif name == "dev.governs":
                value = {"road_id": sign["governs_road"], "lane_id": sign["governs_lane"], "synthetic_fixture": True}
            elif name == "dev.position":
                value = {"station_m": sign["station_m"], "synthetic_fixture": True}
            elif name == "drv.u_turn":
                value = {"requested": r["u_turn_active"], "measured_from_saved_source": None}
            elif name == "drv.turning":
                value = {"requested": r["u_turn_active"], "measured_from_saved_source": None}
            elif name == "kin.speed":
                value = {"velocity_mps": t.get("velocity_mps"), "source": "trace.jsonl"}
            elif name == "kin.heading":
                value = n["native_forward_xy"]
            elif name == "rel.occupies":
                value = n["native_body_xy_m"]
            elif name == "native_body_pose_control":
                value = n
            elif name == "camera_frame_join":
                value = m
            else:
                raise ValueError("Unknown channel: "+name)
            values.append({"time_s": n["time_s"], "value": value})
        write_rows(channels/(name+".jsonl"), values)
    context = root/"context.json"
    expected_context = json.dumps({"signed_hill_crest": {"scope": "synthetic_native_shaped_diagnostic", "sign_authorization_proven": False}}, allow_nan=False)+"\n"
    if context.exists():
        if context.read_text() != expected_context:
            raise ValueError("Existing derived context differs from saved sources")
    else:
        context.write_text(expected_context)


def measure_mounted_turn(root, frames, turn_frames, mounted_turn_frames):
    sources = ("rider_native_samples.jsonl", "authored-sign.json",
               "native_samples.jsonl", "reference_corner.mkv")
    return {"method": "measure_mounted_turn",
            "value": {"frames": frames, "turn_frames": turn_frames,
                      "mounted_turn_frames": mounted_turn_frames,
                      "original_posture_verified": False,
                      "sign_authorization_proven": False},
            "sources": {name: sha(root/name) for name in sources}}


def measure_dismounted_turn(root, frames, dismount_frame, first_turn_frame,
                            walking_turn_frames, turn_frames):
    sources = ("rider_native_samples.jsonl", "authored-sign.json",
               "native_samples.jsonl", "reference_corner.mkv", "trace.jsonl",
               "approach.mkv")
    return {"method": "measure_dismounted_turn",
            "value": {"frames": frames, "dismount_frame": dismount_frame,
                      "first_turn_frame": first_turn_frame,
                      "walking_turn_frames": walking_turn_frames,
                      "turn_frames": turn_frames,
                      "pedestrian_rule_compliance_verified": False,
                      "original_posture_verified": False,
                      "sign_authorization_proven": False},
            "sources": {name: sha(root/name) for name in sources}}


def finalize(attempt, output):
    root, target = Path(attempt), Path(output)
    if target.exists() or (root/"result.json").exists():
        raise ValueError("Retain prior saved result; use a fresh attempt")
    config = json.loads((root/"config.json").read_text())
    kind = config["case_suffix"]
    frames = config["rate_hz"]*config["duration_s"]
    if kind not in ("mounted_obey", "mounted_turn", "dismounted_turn") or config["rate_hz"] != 20 or frames not in (480, 600):
        raise ValueError("Exact rider case/timebase differs")
    native = rows(root/"native_samples.jsonl")
    mapping = rows(root/"video_frames.jsonl")
    rider = rows(root/"rider_native_samples.jsonl")
    trace = rows(root/"trace.jsonl")
    evidence = rows(root/"capture/evidence.jsonl")
    body = rows(root/"body_history.jsonl")
    if any(len(data) != frames for data in (native, mapping, rider, trace, evidence, body)):
        raise ValueError("Original-style frame join incomplete")
    manifest_path = root/"rider-source-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("Missing required source: rider-source-manifest.json")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("source_kind") != "synthetic_native_shaped_diagnostic" or manifest.get("case_suffix") != kind:
        raise ValueError("Unreviewed source kind or case differs")
    if manifest.get("rider_samples_sha256") != sha(root/"rider_native_samples.jsonl"):
        raise ValueError("Rider source hash differs")
    if manifest.get("sign_sha256") != sha(root/"authored-sign.json"):
        raise ValueError("Sign packet hash differs")
    sign = json.loads((root/"authored-sign.json").read_text())
    if (sign.get("code") != "no_u_turn" or sign.get("station_m") != 72.0 or
            sign.get("authorization_proven") is not False):
        raise ValueError("Synthetic sign scope differs")
    turn_frames = mounted_turn_frames = 0
    dismount_frame = None
    first_turn_frame = None
    walking_turn_frames = 0
    for i, (n, m, r, t, e, b) in enumerate(zip(native, mapping, rider, trace, evidence, body)):
        frame, time = n["native_frame"], n["time_s"]
        if (r["frame"] != i or r["time_s"] != time or r["actor_id"] != "rider-1" or
            r["machine_class"] != "bicycle" or r["sign_id"] != sign["id"] or
            r["road_id"] != sign["governs_road"] or r["approach_lane_id"] != sign["governs_lane"]):
            raise ValueError("Rider/sign/frame source join differs")
        if (m["video_frame"] != i or m["native_frame"] != frame or m["carla_frame"] != frame or
            m["time_s"] != time or t["frame"] != frame or e["original_frame"] != frame or
            b["frame"] != frame):
            raise ValueError("Native/source frame identity differs")
        if n["native_center_xy_m"] != [r["x_m"], r["y_m"]]:
            raise ValueError("Rider/Native position differs")
        if {tuple(p) for p in n["native_body_xy_m"]} != {tuple(p[:2]) for p in b["body_vertices_m"]}:
            raise ValueError("Native/body history differs")
        if r["walking_machine"] is r["mounted"]:
            raise ValueError("Rider posture contradicts machine state")
        if not r["mounted"] and dismount_frame is None:
            dismount_frame = i
        if r["u_turn_active"] and first_turn_frame is None:
            first_turn_frame = i
        turn_frames += int(r["u_turn_active"])
        mounted_turn_frames += int(r["u_turn_active"] and r["mounted"])
        walking_turn_frames += int(r["u_turn_active"] and r["walking_machine"])
    expected = kind == "mounted_turn"
    measured = mounted_turn_frames > 0
    if measured != expected or (kind == "mounted_obey" and turn_frames):
        raise ValueError("Controlled mounted-turn source differs")
    if kind == "dismounted_turn":
        if (dismount_frame is None or first_turn_frame is None or
                dismount_frame >= first_turn_frame or mounted_turn_frames or
                walking_turn_frames != turn_frames or
                any(r["mounted"] for r in rider[dismount_frame:])):
            raise ValueError("Dismount-before-turn and persistent walking-machine source differs")
    capture = json.loads((root/"capture/manifest.json").read_text())
    if capture.get("frames") != frames or not capture.get("extraction_confirmed"):
        raise ValueError("Capture extraction incomplete")
    names = ("overview", "approach", "reference_corner", "driver_reference")
    videos = {name+".mkv": video_frames(root/(name+".mkv")) for name in names}
    if any(value != frames for value in videos.values()):
        raise ValueError("Source camera frame count differs")
    description = config["recording_description"]
    rebuild_channels(root, description, native, mapping, rider, trace, sign)
    recording = []
    for channel in description["channels"]:
        reference = "channels/"+channel["name"]+".jsonl"
        if not (root/reference).is_file():
            raise ValueError("Missing required source: "+reference)
        recording.append({"name": channel["name"], "unit": channel["unit"], "reference": reference})
    if not (root/"context.json").is_file():
        raise ValueError("Missing required source: context.json")
    for context in description["context_inputs"]:
        recording.append({"name": context["name"], "unit": context["unit"], "reference": "context.json"})
    result = {"case_id": config["case_id"],
        "measured_values": {"mounted_turn_frames": mounted_turn_frames, "turn_frames": turn_frames,
                            "dismount_frame": dismount_frame, "first_turn_frame": first_turn_frame,
                            "walking_turn_frames": walking_turn_frames,
                            "sign_authorization_proven": False},
        "target_checks": [{"target": "mounted bicycle turns through authored no-U-turn region",
            "requested": expected, "measured": measured,
            "method": "saved synthetic rider/sign/frame joins", "tolerance": "exact boolean source check",
            "matched": expected == measured, "physical_cause_confirmed": False,
            "cause_evidence": ["rider_native_samples.jsonl", "authored-sign.json"]}],
        "setup_confirmed": False, "behavior_attempted": True, "maneuver_completed": True,
        "termination_reason": "full synthetic source duration retained",
        "physical_failure_flags": ["original_rider_posture_sign_authorization_and_pixels_unverified"],
        "trace_reference": "trace.jsonl", "video_references": list(videos),
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description, "recording_evidence": recording,
        "realized_observables": {}, "provenance_kind": "native", "accepted": False,
        "legal_verdict_claimed": False}
    if kind == "dismounted_turn":
        result["target_checks"].append({
            "target": "dismount before U-turn and walk machine through turn",
            "requested": True,
            "measured": dismount_frame is not None and first_turn_frame is not None and
                        dismount_frame < first_turn_frame and walking_turn_frames == turn_frames,
            "method": "saved synthetic rider/frame joins",
            "tolerance": "strict ordering and every turn frame walking",
            "matched": True,
            "physical_cause_confirmed": False,
            "cause_evidence": ["rider_native_samples.jsonl", "native_samples.jsonl"]})
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report = {"format": "c104538-lvmc-synthetic-saved-mounted-diagnostic-v1",
        "case_id": config["case_id"], "candidate_id": config["candidate_id"],
        "source_kind": manifest["source_kind"], "frames": frames, "video_frames": videos,
        "turn_frames": turn_frames, "mounted_turn_frames": mounted_turn_frames,
        "dismount_frame": dismount_frame, "first_turn_frame": first_turn_frame,
        "walking_turn_frames": walking_turn_frames,
        "source_hashes": {name: sha(root/name) for name in
            ("rider_native_samples.jsonl", "authored-sign.json", "native_samples.jsonl",
             "video_frames.jsonl", "capture/manifest.json")},
        "sign_authorization_proven": False, "original_native_capture_executed": False,
        "legal_verdict_claimed": False, "accepted": False,
        "measurements": ({"dismounted_turn_observation": measure_dismounted_turn(
            root, frames, dismount_frame, first_turn_frame, walking_turn_frames, turn_frames)}
            if kind == "dismounted_turn" else
            {"mounted_turn_observation": measure_mounted_turn(root, frames, turn_frames, mounted_turn_frames)})}
    target.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    (root/"result.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
