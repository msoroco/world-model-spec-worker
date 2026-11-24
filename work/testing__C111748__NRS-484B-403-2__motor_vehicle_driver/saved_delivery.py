"""Independent source-integrity audit of a saved U-turn attempt.

This CPU component binds saved sources and can require full video decoding.
It does not establish sign legibility, lawful device status or physical completion.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("device_native_for_saved", ROOT / "native_device.py")
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
CAMERAS = ("overview", "detail_left", "detail_center", "detail_right")
BASE = "testing__C111748__NRS-484B-403-2__motor_vehicle_driver__"
CASES = {BASE + suffix for suffix in ("prohibited_obey", "prohibited_attempt", "neutral_device_turn")}


class DeliverySourceError(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise DeliverySourceError(reason)


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def audit(attempt: Path, *, case_id: str, diagnostic_allowed: bool = False) -> dict:
    """Verify saved original-frame and four-camera references in one attempt."""
    require(case_id in CASES, "unknown exact case")
    attempt = attempt.resolve()
    manifest_path = attempt / "saved-sources.json"
    require(manifest_path.is_file(), "saved source manifest missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest.get("case_id") == case_id, "saved case mismatch")
    require(manifest.get("attempt_id"), "attempt identity missing")
    require(manifest.get("acquisition_kind") == "original_native", "saved acquisition is not original Native")
    require(manifest.get("recording_id"), "recording identity missing")
    native_ref = manifest.get("native", {})
    require(native_ref.get("path") and native_ref.get("sha256"), "Native reference missing")

    def confined(ref):
        path = (attempt / ref).resolve()
        require(path.is_relative_to(attempt) and path.is_file(), "saved source escapes attempt or is missing")
        return path

    native_path = confined(native_ref["path"])
    require(sha_file(native_path) == native_ref["sha256"], "Native source hash mismatch")
    measurement = native.analyze(native_path, case_id=case_id, sha256=native_ref["sha256"])
    packet = json.loads(native_path.read_text(encoding="utf-8"))
    require(not packet.get("diagnostic") or diagnostic_allowed, "diagnostic acquisition cannot support delivery")
    frames = packet["frames"]
    require(len(frames) == 900 and abs(packet.get("duration_s", 0) - 45.0) < 1e-9,
            "delivery needs 900 original frames at 20 Hz")
    first_t = frames[0]["time_s"]
    for i, row in enumerate(frames):
        require(abs((row["time_s"] - first_t) - i / 20.0) <= 0.002, "original 20 Hz time drift")
        require(set(row.get("cameras", {})) == set(CAMERAS), "four original camera identities missing")
        require(all(row["cameras"][name] == row["frame"] for name in CAMERAS),
                "camera and Native frame identities differ")
    media = manifest.get("media", {})
    require(set(media) == set(CAMERAS), "four saved camera sources missing")
    hashes = {}
    for name in CAMERAS:
        ref = media[name]
        require(isinstance(ref, dict) and ref.get("path") and ref.get("sha256"),
                f"{name} media reference missing")
        path = confined(ref["path"])
        actual = sha_file(path)
        require(actual == ref["sha256"], f"{name} media hash mismatch")
        hashes[name] = actual
    suffix = case_id.removeprefix(BASE)
    require(measurement["turn_observed"] == (suffix != "prohibited_obey"),
            "Native action does not match exact case")
    require(measurement["prohibits_u_turn"] == (suffix != "neutral_device_turn"),
            "Native display does not match exact case")
    return {"format": "worker-saved-source-integrity", "case_id": case_id,
            "attempt_id": manifest["attempt_id"], "recording_id": manifest["recording_id"],
            "native_sha256": native_ref["sha256"], "media_sha256": hashes,
            "frame_count": len(frames), "native_source": True, "time_join": True,
            "all_participants": False, "full_video_decode": False,
            "actual_pixels": False, "physical_completion": False,
            "legal_device_status": "requires_independent_source_review"}


def audit_complete(attempt: Path, *, case_id: str, profile: dict | None = None) -> dict:
    """Require source integrity and four complete lossless video decodes.

    This saved-only path is separate from physical and pixel review. Importing
    the decoder here avoids a module import cycle with its source audit call.
    """
    spec = importlib.util.spec_from_file_location("device_video_for_saved_delivery",
                                                   ROOT / "saved_video_audit.py")
    video = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(video)
    decoded = video.audit(attempt, case_id=case_id, profile=profile)
    require(decoded.get("full_video_decode") is True and
            len(decoded.get("decoded_media", {})) == len(CAMERAS) and
            all(row.get("frame_count") == 900 for row in decoded["decoded_media"].values()),
            "complete four-camera decode missing")
    return {**decoded, "format": "worker-saved-source-and-video-integrity",
            "actual_pixels": False, "physical_completion": False,
            "legal_device_status": "requires_independent_source_review"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--attempt", type=Path, required=True)
    ap.add_argument("--case", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--full-decode", action="store_true")
    args = ap.parse_args()
    result = (audit_complete(args.attempt, case_id=args.case) if args.full_decode
              else audit(args.attempt, case_id=args.case))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
