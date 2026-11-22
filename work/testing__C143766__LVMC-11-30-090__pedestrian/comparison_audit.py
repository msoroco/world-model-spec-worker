"""Independent source-bound audit of diagnostic pedestrian route pairs."""
from __future__ import annotations

import json
from pathlib import Path

from corridor_construction import compare_authored_routes
from saved_measurement import _verified, measure_saved
from delivery_audit import audit as audit_delivery, rows as delivery_rows, sha


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


def audit_delivery_pair(first_attempt, second_attempt, *, diagnostic_test=False):
    """Independently compare two sealed delivered attempts and their decoded media."""
    roots = [Path(first_attempt).resolve(), Path(second_attempt).resolve()]
    receipts = [audit_delivery(root, diagnostic_test=diagnostic_test) for root in roots]
    scenes = [json.loads((root/"scene.json").read_text()) for root in roots]
    authored = compare_authored_routes(scenes[0], scenes[1], True)
    if [receipt["case_id"] for receipt in receipts] != [scene["case_id"] for scene in scenes]:
        raise ValueError("paired delivery case identity differs")
    histories = [delivery_rows(root/"walker-body-history.jsonl") for root in roots]
    if len(histories[0]) != len(histories[1]):
        raise ValueError("paired original frame counts differ")
    if [(row["frame"], row["time_s"]) for row in histories[0]] != [
            (row["frame"], row["time_s"]) for row in histories[1]]:
        raise ValueError("paired original frame and time identities differ")
    for left, right in zip(*histories):
        x_left = [point[0] for point in left["body_xy_m"]]
        x_right = [point[0] for point in right["body_xy_m"]]
        if any(abs(a-b) > (.5 if not diagnostic_test else 1e-9)
               for a, b in zip(x_left, x_right)):
            raise ValueError("paired longitudinal original bodies differ")
        y_left = [point[1] for point in left["body_xy_m"]]
        y_right = [point[1] for point in right["body_xy_m"]]
        shift = y_right[0]-y_left[0]
        if abs(shift) < .5 or any(abs((b-a)-shift) > (.5 if not diagnostic_test else 1e-9)
                                    for a, b in zip(y_left, y_right)):
            raise ValueError("paired lateral body change is not isolated")
    if not diagnostic_test and any(receipt["physical_completion_status"] != "met"
                                   for receipt in receipts):
        raise ValueError("paired Native physical completion not established")
    return {"format": "c143766-paired-delivery-audit-v1",
            "case_ids": [scene["case_id"] for scene in scenes],
            "map_sha256": scenes[0]["map_source_sha256"],
            "body_history_sha256": [sha(root/"walker-body-history.jsonl") for root in roots],
            "capture_seal_sha256": [receipt["capture_seal_sha256"] for receipt in receipts],
            "authored": authored, "frame_count": len(histories[0]),
            "four_view_full_decode_passed": True,
            "diagnostic_audit_test_passed": diagnostic_test,
            "physical_acceptance_claimed": False,
            "actual_pixel_visibility_verified": False,
            "legal_judgment": "unresolved"}
