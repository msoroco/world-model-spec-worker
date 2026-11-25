"""Independent source, frame and four-camera audit for a rail-stop attempt."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from rail_stop_audit import audit_saved_file
from native_construction import verify_production_site

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CAMERA_SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
                "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
SOURCES = ("rail-stop-packet.json", "native-crossing-geometry.json",
           "native-authority-record.json", "native-stop-device.json",
           "native-ego-kinematics.json", "native-ego-footprint.json",
           "trace.jsonl", "video_frames.jsonl")
NATIVE_ORIGINALS = (*SOURCES, "config.json", "construction.json",
                    "acquisition-provenance.json", "camera-frame-joins.json",
                    "pixel-sample-inventory.json", *(name + ".mkv" for name in CAMERAS))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _decoded_bgra(video: Path, index: int, *, png: bool = False) -> bytes:
    command = ["ffmpeg", "-nostdin", "-v", "error", "-i", str(video)]
    if not png:
        command.extend(["-vf", f"select=eq(n\\,{index})", "-vsync", "0"])
    command.extend(["-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "bgra", "pipe:1"])
    return subprocess.check_output(command, timeout=120)


def _verify_native_pixel_samples(attempt: Path, seal: dict, mapping: list) -> dict:
    inventory = json.loads((attempt / "pixel-sample-inventory.json").read_text())
    joins = json.loads((attempt / "camera-frame-joins.json").read_text())
    expected = {(camera, index) for camera in CAMERAS for index in (0, 450, 899)}
    rows = inventory.get("samples", [])
    if inventory.get("frames") != [0, 450, 899] or len(joins) != 900 or len(rows) != len(expected):
        raise ValueError("original PNG sample inventory incomplete")
    for index, joined in enumerate(joins):
        if (joined.get("frame") != index
                or joined.get("source_frame") != mapping[index]["carla_frame"]
                or set(joined.get("cameras", {})) != set(CAMERAS)):
            raise ValueError("original camera frame joins incomplete")
        for name in CAMERAS:
            camera = joined["cameras"][name]
            if (camera.get("frame") != joined["source_frame"]
                    or camera.get("source_video") != name + ".mkv"
                    or (camera.get("width"), camera.get("height")) != CAMERA_SIZES[name]
                    or len(camera.get("original_bgra_sha256", "")) != 64):
                raise ValueError("original camera source hash join differs")
    if {(r.get("camera"), r.get("video_frame")) for r in rows} != expected:
        raise ValueError("original PNG sample coverage differs")
    verified = {}
    for row in rows:
        name, index = row["camera"], row["video_frame"]
        png_name = f"original-{name}-{index:03d}.png"
        if row.get("png") != png_name or png_name not in seal["sources"]:
            raise ValueError("unsealed original PNG sample")
        joined = joins[index]
        camera = joined["cameras"][name]
        if (joined.get("frame") != index or row.get("source_frame") != joined.get("source_frame")
                or camera.get("original_bgra_sha256") != row.get("original_bgra_sha256")):
            raise ValueError("original PNG/frame source join differs")
        original_hash = row["original_bgra_sha256"]
        png_pixels = _decoded_bgra(attempt / png_name, index, png=True)
        video_pixels = _decoded_bgra(attempt / (name + ".mkv"), index)
        if not png_pixels or hashlib.sha256(png_pixels).hexdigest() != original_hash:
            raise ValueError("original PNG pixels differ: " + png_name)
        if video_pixels != png_pixels:
            raise ValueError("original PNG/video pixels differ: " + png_name)
        verified[png_name] = {"source_frame": row["source_frame"],
                              "video_frame": index, "bgra_sha256": original_hash}
    return verified


def _independent_review(attempt: Path, seal: dict, joins: dict,
                        measurement: dict | None = None) -> dict:
    path = attempt / "independent-physical-review.json"
    if not path.is_file():
        raise ValueError("independent original-frame physical review missing")
    review = json.loads(path.read_text())
    if (review.get("format") != "rail-stop-independent-physical-review"
            or review.get("reviewer_role") != "independent_physical_reviewer"
            or not review.get("reviewer") or not review.get("reviewed_at")
            or review.get("capture_seal_sha256") != sha(attempt / "capture-seal.json")
            or review.get("original_png_video_joins") != joins):
        raise ValueError("independent physical review is unbound or incomplete")
    required = ("crossing_and_nearest_rail", "official_stop_device_and_authority",
                "ego_body_stop_footprint", "cessation", "departure_clearance")
    checks = review.get("checks")
    if not isinstance(checks, dict) or set(checks) != set(required):
        raise ValueError("independent physical review lacks required scene checks")
    for name in required:
        value = checks[name]
        if (not isinstance(value, dict) or value.get("status") != "verified"
                or not value.get("original_frame_refs") or not value.get("finding")):
            raise ValueError("independent original-frame review did not verify: " + name)
        for ref in value["original_frame_refs"]:
            if ref in joins:
                continue
            parts = ref.split(":") if isinstance(ref, str) else []
            if (len(parts) != 3 or parts[0] != "video" or parts[1] not in CAMERAS
                    or not parts[2].isdigit() or int(parts[2]) >= 900):
                raise ValueError("independent review references an unjoined original frame")
            if parts[1] + ".mkv" not in seal["sources"]:
                raise ValueError("independent review references an unsealed video")
    if measurement and measurement.get("first_stop_frame") is not None:
        stop = measurement["first_stop_frame"]
        for name in ("ego_body_stop_footprint", "cessation"):
            refs = checks[name]["original_frame_refs"]
            if not any(ref == f"video:{camera}:{stop}" for camera in CAMERAS for ref in refs):
                raise ValueError("independent review omitted measured stop frame: " + name)
        if measurement.get("proceeding_observed"):
            refs = checks["departure_clearance"]["original_frame_refs"]
            if not any(isinstance(ref, str) and ref.startswith("video:")
                       and int(ref.rsplit(":", 1)[1]) > stop for ref in refs):
                raise ValueError("independent review omitted post-stop departure frame")
    return review


def audit(attempt: Path, *, diagnostic_test: bool = False) -> dict:
    attempt = Path(attempt).resolve()
    config = json.loads((attempt / "config.json").read_text())
    provenance = json.loads((attempt / "acquisition-provenance.json").read_text())
    seal = json.loads((attempt / "capture-seal.json").read_text())
    if not isinstance(seal.get("sources"), dict):
        raise ValueError("capture source seal missing")
    synthetic = provenance.get("provenance_kind") == "synthetic_fixture"
    if provenance.get("provenance_kind") not in ("native", "synthetic_fixture"):
        raise ValueError("unknown capture provenance")
    if provenance.get("provenance_kind") != seal.get("provenance_kind"):
        raise ValueError("capture provenance and seal differ")
    required_sealed = set(SOURCES) | {name + ".mkv" for name in CAMERAS}
    if (attempt / "native-conflict-history.json").is_file():
        required_sealed.add("native-conflict-history.json")
    if not synthetic:
        if (seal.get("frames") != 900 or seal.get("diagnostic_fixture") is not False
                or seal.get("restoration", {}).get("restored") is not True
                or set(seal.get("encoder_exit_codes", {})) != set(CAMERAS)
                or any(code != 0 for code in seal["encoder_exit_codes"].values())
                or not {"capture_finished", "encoders_closed", "restoration_verified"}
                <= set(seal.get("events", []))
                or seal.get("physical_acceptance_claimed") is not False):
            raise ValueError("Native capture seal lacks complete restored acquisition")
        required_sealed |= set(NATIVE_ORIGINALS)
        required_sealed.add("site/packet.json")
        site_path = attempt / "site/packet.json"
        if site_path.is_file():
            site_packet = json.loads(site_path.read_text())
            for binding in site_packet.get("sources", {}).values():
                required_sealed.add("site/" + binding["path"])
        required_sealed |= {f"original-{name}-{index:03d}.png"
                            for name in CAMERAS for index in (0, 450, 899)}
    if not required_sealed <= set(seal["sources"]):
        raise ValueError("capture seal lacks complete original source inventory")
    for name, checksum in seal["sources"].items():
        path = (attempt / name).resolve()
        if not path.is_relative_to(attempt):
            raise ValueError("capture seal escapes original attempt")
        if not path.is_file() or sha(path) != checksum:
            raise ValueError("sealed original source changed: " + name)
    if config["selected_case_id"] != config["case"]["case_id"]:
        raise ValueError("selected case identity differs")
    if not synthetic:
        verify_production_site(attempt / "site/packet.json", config["case"])
    measurement = audit_saved_file(attempt / "rail-stop-packet.json")
    if measurement.get("status") != "measured":
        raise ValueError("original rail-stop measurement is incomplete")
    packet = json.loads((attempt / "rail-stop-packet.json").read_text())
    if any(binding.get("path") not in seal["sources"]
           for binding in packet.get("sources", {}).values()):
        raise ValueError("rail measurement used an unsealed original source")
    trace = [json.loads(line) for line in (attempt / "trace.jsonl").read_text().splitlines()]
    mapping = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines()]
    if len(trace) != 900 or len(mapping) != 900:
        raise ValueError("900 original frames required")
    for index, (motion, frame) in enumerate(zip(trace, mapping)):
        if (frame.get("video_frame") != index or motion.get("frame") != frame.get("carla_frame")
                or motion.get("time_s") != frame.get("time_s")):
            raise ValueError("original trace/video frame join differs")
    decoded = {}
    for name in CAMERAS:
        video = attempt / (name + ".mkv")
        if not video.is_file():
            raise ValueError("original camera missing: " + name)
        probe = json.loads(subprocess.check_output([
            "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
            "-show_entries", "stream=nb_read_frames,width,height", "-of", "json", str(video)], text=True))
        stream = probe["streams"][0]
        count = int(stream["nb_read_frames"])
        if count != 900 or (stream.get("width"), stream.get("height")) != CAMERA_SIZES[name]:
            raise ValueError("original camera frame count or size differs: " + name)
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(video),
                        "-f", "null", "-"], check=True, stdout=subprocess.DEVNULL,
                       timeout=180)
        decoded[name] = {"frames": count, "sha256": sha(video)}
    joined_pixels = {}
    review = None
    if not synthetic:
        joined_pixels = _verify_native_pixel_samples(attempt, seal, mapping)
        review = _independent_review(attempt, seal, joined_pixels, measurement)
    if diagnostic_test:
        if not synthetic or provenance.get("diagnostic_fixture") is not True:
            raise ValueError("diagnostic test requires synthetic provenance")
    elif synthetic:
        raise ValueError("synthetic diagnostic cannot pass Native delivery")
    return {"case_id": config["selected_case_id"],
            "source_hashes": {name: sha(attempt / name) for name in SOURCES},
            "nearest_rail_measurement": measurement,
            "camera_decode": decoded, "original_frame_count": 900,
            "original_png_video_joins": joined_pixels,
            "independent_review_sha256": sha(attempt / "independent-physical-review.json") if review else None,
            "diagnostic_audit_test_passed": diagnostic_test,
            "delivery_physical_audit_passed": bool(review),
            "actual_carla_capture_claimed": bool(review)}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Audit one sealed original rail-stop attempt")
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--diagnostic-test", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, diagnostic_test=args.diagnostic_test),
                     separators=(",", ":")))


if __name__ == "__main__":
    main()
