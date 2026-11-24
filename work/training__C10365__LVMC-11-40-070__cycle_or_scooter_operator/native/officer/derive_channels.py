"""Reconstruct diagnostic observations from retained rider, officer and frame sources."""
import hashlib
import json
from pathlib import Path

from saved import process, read_rows


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def derive(bundle, raw, video, review, output, *, synthetic=False):
    bundle, raw, video, review, output = map(Path, (bundle, raw, video, review, output))
    if output.exists():
        raise ValueError("Derived channel output already exists")
    if (raw.parent / "channels").exists():
        raise ValueError("Injected channels are not retained Native sources")
    summary = process(bundle, raw, video, review, synthetic=synthetic)
    source_hashes = {name: sha(path) for name, path in
                     (("raw", raw), ("video_frames", video), ("visual_review", review),
                      ("config", bundle / "config.json"),
                      ("requested_tracks", bundle / "requested-tracks.jsonl"))}
    native_rows, video_rows = read_rows(raw), read_rows(video)
    visual = json.loads(review.read_text())
    channels = {name: [] for name in (
        "rider_body", "officer_body", "kin.velocity", "dev.stop_sign",
        "dev.governs", "dev.human_direction", "rider_response",
        "native_frame_join", "camera_frame_join")}
    for row, mapped in zip(native_rows, video_rows):
        time_s = row["time_s"]
        values = {
            "rider_body": row["rider"],
            "officer_body": row["officer_actor"],
            "kin.velocity": row["rider"]["speed_mps"],
            "dev.stop_sign": {"id": visual["device_id"], "stop_station_x_m": 50.0},
            "dev.governs": {"applicable_reviewed": visual["device_applicable"],
                            "source_kind": visual["source_kind"]},
            "dev.human_direction": {"direction_reviewed": visual["officer_direction"],
                                    "authority_reviewed": visual.get("officer_authority_reviewed", False),
                                    "visible": visual.get("direction_visible", False)},
            "rider_response": {"front_x_m": max(p[0] for p in row["rider"]["body_native_xyz_m"]),
                               "speed_mps": row["rider"]["speed_mps"]},
            "native_frame_join": {"native_frame": row["native_frame"],
                                  "source_kind": row["source_kind"]},
            "camera_frame_join": mapped,
        }
        for name, value in values.items():
            channels[name].append({"time_s": time_s, "value": value})
    output.mkdir(parents=True)
    hashes = {}
    for name, rows in sorted(channels.items()):
        path = output / (name + ".jsonl")
        path.write_text("".join(json.dumps(item, sort_keys=True, allow_nan=False) + "\n"
                                for item in rows))
        hashes[name] = sha(path)
    receipt = {"format": "c10365-source-derived-channels-v1", "frames": len(native_rows),
               "source_hashes": source_hashes, "channel_hashes": hashes,
               "source_kind": summary["source_kind"], "diagnostic_only": True,
               "physical_legal_verdict": None}
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if any(sha(path) != source_hashes[name] for name, path in
           (("raw", raw), ("video_frames", video), ("visual_review", review))):
        raise ValueError("Derivation changed retained source")
    return receipt
