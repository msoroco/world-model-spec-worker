"""Install an operator-supplied reviewed site into a materialized Native attempt.

The intake is structural. It cannot attest to the truth of a review declaration.
"""
import hashlib
import json
import os
from pathlib import Path

from reviewed_site_intake import NAMES, SOURCE_KEYS, check


CASE_PACKET = {
    "reverse_over_crosswalk": NAMES[0],
    "reverse_stops_before_crosswalk": NAMES[0],
    "reverse_into_intersection": NAMES[1],
    "reverse_stops_before_intersection": NAMES[2],
    "reverse_around_street_corner": NAMES[3],
    "reverse_stops_before_street_corner": NAMES[4],
}


def install(output, case_id):
    bundle_name = os.environ.get("C215286_REVIEW_BUNDLE")
    if not bundle_name:
        return None
    output = Path(output).resolve()
    if not (output / "construction.json").is_file():
        raise ValueError("Materialized exact construction required")
    suffix = case_id.rsplit("__", 1)[-1]
    if suffix not in CASE_PACKET:
        raise ValueError("Unknown selected case for reviewed site install")
    bundle = Path(bundle_name).resolve(strict=True)
    receipt = check(bundle)
    name = CASE_PACKET[suffix]
    packet = json.loads((bundle / name).read_text(encoding="utf-8"))
    existing = output / ("site_packet.json" if name == NAMES[0] else "site_templates/" + name)
    materialized = json.loads(existing.read_text(encoding="utf-8"))
    if name != NAMES[0] and packet.get("vehicle_blueprint_id") != materialized.get("vehicle_blueprint_id"):
        raise ValueError("Reviewed site must bind selected candidate blueprint")
    paths = [name] + [packet[key]["path"] for key in SOURCE_KEYS[name]]
    targets = []
    for relative in paths:
        rel = Path(relative)
        target = output / rel
        source = bundle / rel
        if target.resolve().is_relative_to(output) is False or source.resolve().is_relative_to(bundle) is False:
            raise ValueError("Reviewed site source escapes attempt")
        content = source.read_bytes()
        if len(content) > 2 * 1024 * 1024:
            raise ValueError("Reviewed site source oversized")
        targets.append((target, content))
    # All checks above finish before the first original source is replaced.
    for target, content in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    installed = output / name
    if name != NAMES[0]:
        # The alternative runner reads the root copy as the original capture source.
        installed.write_bytes((bundle / name).read_bytes())
    if hashlib.sha256(installed.read_bytes()).hexdigest() != receipt["site_packets"][name]["sha256"]:
        raise ValueError("Installed site packet changed")
    return {"case_id": case_id, "source_bundle": str(bundle), "site_packet": name,
            "site_packet_sha256": receipt["site_packets"][name]["sha256"],
            "intake_status": receipt["status"], "physical_acceptance_claimed": False}
