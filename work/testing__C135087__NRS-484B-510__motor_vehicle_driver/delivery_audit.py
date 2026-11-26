"""Source-bound external pixel review of a restricted-zone Native attempt.

Physical completion means the listed phenomena were independently seen in
original pixels. This audit makes no statutory interference determination.
"""

import hashlib
import json
import subprocess
from pathlib import Path

from saved_audit import VIEWS, audit as audit_saved


OBSERVATIONS = ("restricted_zone_sign", "zone_boundaries", "passenger_vehicle",
                "passenger_exchange", "restricted_purpose_entrant", "entrant_approach",
                "entrant_waiting_or_access", "subject_zone_dwell", "four_camera_visibility")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _decode_media(attempt):
    """Decode every selected encoded frame; source PNG custody is checked separately."""
    counts = {}
    for name in (*VIEWS, "raw"):
        media = attempt / (name + ".mkv")
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                "-show_entries", "stream=width,height,avg_frame_rate",
                                "-of", "json", str(media)], capture_output=True, text=True)
        if probe.returncode:
            raise ValueError("encoded media probe failed: " + name)
        streams = json.loads(probe.stdout).get("streams", [])
        if len(streams) != 1 or streams[0].get("width", 0) <= 0 or streams[0].get("height", 0) <= 0:
            raise ValueError("encoded media video stream invalid: " + name)
        decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(media),
                                  "-map", "0:v:0", "-progress", "pipe:1", "-nostats",
                                  "-f", "null", "-"],
                                 capture_output=True, text=True)
        if decoded.returncode:
            raise ValueError("encoded media full decode failed: " + name)
        frames = [int(line.partition("=")[2]) for line in decoded.stdout.splitlines()
                  if line.startswith("frame=")]
        if not frames or frames[-1] != 900:
            raise ValueError("encoded media frame count mismatch: " + name)
        counts[name] = frames[-1]
    return counts


def audit(attempt, case_id, expected_site_sha256, review_path, expected_review_sha256):
    attempt = Path(attempt).resolve()
    review_path = Path(review_path).resolve()
    if attempt == review_path or attempt in review_path.parents:
        raise ValueError("independent reviewer packet must be outside attempt")
    if not review_path.is_file() or not expected_review_sha256 or _sha(review_path) != expected_review_sha256:
        raise ValueError("independent reviewer packet missing or stale")
    saved = audit_saved(attempt, case_id, expected_site_sha256)
    if saved["diagnostic_fixture"]:
        raise ValueError("diagnostic fixture cannot satisfy original delivery")
    decoded_media = _decode_media(attempt)
    review = json.loads(review_path.read_text())
    if review.get("case_id") != case_id or review.get("site_packet_sha256") != expected_site_sha256:
        raise ValueError("external reviewer case/site mismatch")
    if not review.get("reviewer") or not review.get("reviewed_at"):
        raise ValueError("external reviewer identity missing")
    observations = review.get("observations")
    if not isinstance(observations, dict) or set(observations) != set(OBSERVATIONS):
        raise ValueError("physical observation review incomplete")
    history = [json.loads(line) for line in (attempt / "original-attempt/history.jsonl").read_text().splitlines()]
    for topic, item in observations.items():
        if not isinstance(item, dict) or item.get("observed") is not True or not item.get("note"):
            raise ValueError("physical observation unconfirmed: " + topic)
        index, view = item.get("frame"), item.get("view")
        if type(index) is not int or not 0 <= index < 900 or view not in VIEWS:
            raise ValueError("physical observation frame/view invalid: " + topic)
        if history[index]["camera_sources"][view]["sha256"] != item.get("pixel_sha256"):
            raise ValueError("physical observation pixel citation stale: " + topic)
    return {"case_id": case_id, "site_packet_sha256": expected_site_sha256,
            "review_sha256": expected_review_sha256, "observed_topics": list(OBSERVATIONS),
            "encoded_media": decoded_media,
            "physical_completion": True, "legal_status": "unresolved_judgment"}
