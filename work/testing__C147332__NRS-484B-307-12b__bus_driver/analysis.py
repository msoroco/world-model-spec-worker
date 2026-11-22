"""Source-bound saved finalizer for the C147332 red-X bus probes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lane_signal_measurement import measure
from source_review import validate as validate_site


CHANNELS = ("bus-body-history.jsonl", "lane-signal-history.jsonl", "camera-frame-map.jsonl")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError("original channel has no frames: " + path.name)
    return rows


def _recorded_sha(acquisition, name):
    value = acquisition.get(name)
    return value.get("sha256") if isinstance(value, dict) else value


def build_report(attempt):
    attempt = Path(attempt)
    acquisition = json.loads((attempt / "acquisition.json").read_text())
    site = validate_site(attempt / "source-review.json", source_root=attempt)
    if _recorded_sha(acquisition, "source-review.json") != _sha(attempt / "source-review.json"):
        raise ValueError("site review packet is not bound to original acquisition")
    streams = []
    for name in CHANNELS:
        path = attempt / name
        digest = _sha(path)
        if _recorded_sha(acquisition, name) != digest:
            raise ValueError("original channel missing or changed: " + name)
        rows = _rows(path)
        verified_rows = []
        for row in rows:
            source_name = row.get("source_path")
            if (not isinstance(source_name, str) or not source_name or
                    Path(source_name).is_absolute() or ".." in Path(source_name).parts):
                raise ValueError("original channel row source path missing: " + name)
            source = attempt / source_name
            source_digest = _recorded_sha(acquisition, source_name)
            if (not source.is_file() or source_digest != _sha(source) or
                    (row.get("source_sha256") is not None and
                     row["source_sha256"] != source_digest)):
                raise ValueError("original channel row source missing or changed: " + name)
            verified_rows.append({**row, "source_sha256": source_digest})
        streams.append(verified_rows)
    if len({len(rows) for rows in streams}) != 1:
        raise ValueError("original channels have different frame counts")
    joined = []
    for body, signal, camera in zip(*streams):
        if signal.get("official_device_source_sha256") != site["official_device_source_sha256"]:
            raise ValueError("signal observation differs from reviewed device source")
        joined.append({"frame": body.get("frame"), "elapsed_seconds": body.get("elapsed_seconds"),
                       "body": body, "lane_signal": signal, "camera_frame": camera})
    return {"format": "c147332-saved-measurement", "site_review": site,
            "measurements": {"red_x_bus_lane": measure(joined)},
            "source_hashes": {name: _recorded_sha(acquisition, name) for name in CHANNELS},
            "legal_judgment": "unresolved", "physical_acceptance_claimed": False}
