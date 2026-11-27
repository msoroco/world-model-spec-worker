"""Review packet gate for the exact nighttime nonmotor parking branch.

The packet records review findings and hashes of the original supporting files.
It does not infer legal classification from a CARLA blueprint or a case label.
"""

import argparse
import hashlib
import json
from pathlib import Path


FIELDS = (
    "transport_capability",
    "excluded_device",
    "self_propulsion",
    "responsible_person",
    "parking_purpose",
    "active_loading_or_unloading",
    "street_public_access",
    "city_limits",
    "civil_clock",
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(path, *, require_original=False):
    path = Path(path).resolve()
    packet = json.loads(path.read_text())
    if packet.get("format") != "c229398-source-review-v1":
        raise ValueError("Wrong review packet format")
    if packet.get("case_id") is None or not packet["case_id"].endswith(
            ("__below_30", "__at_30", "__above_30")):
        raise ValueError("Wrong exact case identity")
    kind = packet.get("source_kind")
    if kind not in ("synthetic_cpu", "original_review"):
        raise ValueError("Missing review provenance")
    if require_original and kind != "original_review":
        raise ValueError("Original review required before Native acceptance")
    findings = packet.get("findings")
    if not isinstance(findings, dict) or set(findings) != set(FIELDS):
        raise ValueError("Incomplete qualifying context review")
    sources = packet.get("sources")
    if not isinstance(sources, dict) or set(sources) != set(FIELDS):
        raise ValueError("Each finding needs its own source binding")
    root = path.parent
    for field in FIELDS:
        item = sources[field]
        if not isinstance(item, dict) or not all(item.get(k) for k in
                                                  ("path", "sha256", "citation")):
            raise ValueError("Missing cited source: " + field)
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe cited source path: " + field)
        source_path = (root / relative).resolve()
        if root not in source_path.parents or not source_path.is_file():
            raise ValueError("Cited source missing: " + field)
        if digest(source_path) != item["sha256"]:
            raise ValueError("Cited source hash differs: " + field)
        if kind == "original_review" and item.get("source_kind") != "original":
            raise ValueError("Original source required: " + field)
    if not isinstance(findings["transport_capability"], bool) or not isinstance(
            findings["excluded_device"], bool) or not isinstance(
            findings["self_propulsion"], bool):
        raise ValueError("Device classification must be reviewed")
    if not isinstance(findings["responsible_person"], str) or not findings[
            "responsible_person"].strip():
        raise ValueError("Responsible person not established")
    if findings["parking_purpose"] not in ("park", "stop", "stand", "unknown"):
        raise ValueError("Parking activity unresolved")
    for field in ("active_loading_or_unloading", "street_public_access",
                  "city_limits"):
        if not isinstance(findings[field], bool):
            raise ValueError("Source finding unresolved: " + field)
    clock = findings["civil_clock"]
    if not isinstance(clock, dict) or not clock.get("iana_timezone") or not clock.get(
            "utc_start_ms") or not isinstance(clock.get("utc_start_ms"), int):
        raise ValueError("Civil clock source unresolved")
    eligible = (findings["transport_capability"] and not findings["excluded_device"]
                and not findings["self_propulsion"] and findings["parking_purpose"] == "park"
                and not findings["active_loading_or_unloading"]
                and findings["street_public_access"] and findings["city_limits"])
    return {"format": "c229398-source-gate-v1", "case_id": packet["case_id"],
            "packet_sha256": digest(path), "source_kind": kind,
            "qualifying_context_supported": eligible,
            "physical_or_legal_acceptance": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", required=True)
    parser.add_argument("--require-original", action="store_true")
    arguments = parser.parse_args()
    print(json.dumps(audit(arguments.packet, require_original=arguments.require_original)))


if __name__ == "__main__":
    main()
