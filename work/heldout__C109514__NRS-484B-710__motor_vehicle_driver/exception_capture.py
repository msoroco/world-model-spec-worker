"""Retain actor-bound dispatch premises from original operator source packets.

The packets are local inputs staged for the capture. Their assertions remain
subject to independent review; a vehicle blueprint or lamp is not authority.
"""

from hashlib import sha256
import json
from pathlib import Path


PACKETS = {
    "authorized_emergency": "authorization.json",
    "official_business": "official_business.json",
}


def retain_exception_source(output, ego_id, context):
    output = Path(output)
    keys = {
        "authorized_emergency": "subject_authorized_emergency",
        "official_business": "subject_official_business",
    }
    if not any(context.get(key) for key in keys.values()):
        return None
    if not isinstance(ego_id, int):
        raise ValueError("Native subject actor ID is required")
    source = {"ego_id": ego_id}
    for premise, context_key in keys.items():
        assertion = context.get(context_key)
        if type(assertion) is not bool:
            raise ValueError("Exception premise must be an explicit boolean: " + premise)
        packet = output / "source_packets" / PACKETS[premise]
        if not packet.is_file():
            raise ValueError("Missing original exception packet: " + str(packet))
        raw = packet.read_bytes()
        try:
            row = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Invalid original exception packet: " + premise) from error
        if row.get("ego_id") != ego_id or row.get("asserted") is not assertion:
            raise ValueError("Exception packet actor or assertion differs: " + premise)
        citation = row.get("source_ref")
        if not isinstance(citation, str) or not citation.strip():
            raise ValueError("Exception packet lacks source reference: " + premise)
        source[premise] = {
            "asserted": assertion,
            "source_ref": citation,
            "packet": "source_packets/" + PACKETS[premise],
            "packet_sha256": sha256(raw).hexdigest(),
        }
    target = output / "subject_exception_source.json"
    if target.exists():
        raise ValueError("Retain prior subject exception source; use a fresh attempt")
    target.write_text(json.dumps(source, indent=2, allow_nan=False) + "\n")
    return target
