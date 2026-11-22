"""Independent source-bound audit of diagnostic pedestrian route pairs."""
from __future__ import annotations

import json
from pathlib import Path

from corridor_construction import compare_authored_routes
from saved_measurement import _verified, measure_saved


def audit_pair(root, first_manifest, second_manifest, *, declared_band_change):
    root = Path(root)
    manifests = [json.loads(Path(path).read_text()) for path in (first_manifest, second_manifest)]
    scenes = [json.loads(_verified(root, item["scene"])) for item in manifests]
    authored = compare_authored_routes(scenes[0], scenes[1], declared_band_change)
    saved = [measure_saved(root, path) for path in (first_manifest, second_manifest)]
    if saved[0]["map_sha256"] != saved[1]["map_sha256"]:
        raise ValueError("comparison map source changed")
    histories = [[json.loads(line) for line in _verified(root, item["body_history"]).decode().splitlines() if line]
                 for item in manifests]
    if len(histories[0]) != len(histories[1]):
        raise ValueError("comparison frame counts differ")
    first, second = histories
    if [row["frame"] for row in first] != [row["frame"] for row in second]:
        raise ValueError("comparison frame identities differ")
    if [row["time_s"] for row in first] != [row["time_s"] for row in second]:
        raise ValueError("comparison frame times differ")
    for a, b in zip(first, second):
        xs1 = [point[0] for point in a["body_xy_m"]]
        xs2 = [point[0] for point in b["body_xy_m"]]
        if xs1 != xs2:
            raise ValueError("comparison longitudinal original bodies differ")
        ys1 = [point[1] for point in a["body_xy_m"]]
        ys2 = [point[1] for point in b["body_xy_m"]]
        delta = ys2[0] - ys1[0]
        if abs(delta) < .5 or any(abs((y2-y1)-delta) > 1e-9 for y1, y2 in zip(ys1, ys2)):
            raise ValueError("comparison lateral original bodies are not an isolated translation")
    bands = [scenes[0]["route_band"], scenes[1]["route_band"]]
    for item, band in zip(saved, bands):
        counts = item["measurement"]["band_overlap_frame_counts"]
        if counts[band] != item["measurement"]["frames"]:
            raise ValueError("original body does not traverse its authored band")
    return {"case_ids": [item["case_id"] for item in saved],
            "map_sha256": saved[0]["map_sha256"],
            "body_history_sha256": [item["body_history_sha256"] for item in saved],
            "authored": authored, "original_lateral_difference_measured": True,
            "physical_acceptance_claimed": False, "legal_judgment": "unresolved"}
