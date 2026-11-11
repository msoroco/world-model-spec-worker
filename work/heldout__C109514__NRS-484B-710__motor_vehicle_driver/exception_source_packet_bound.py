"""Check the retained exception assertion against both original packets."""

from hashlib import sha256
import json
from pathlib import Path


def read_exception_source(root, context, ego_id):
    if not (context["subject_authorized_emergency"] or context["subject_official_business"]):
        return None
    root = Path(root)
    path = root / "subject_exception_source.json"
    if not path.is_file():
        raise ValueError("Missing required source: subject_exception_source.json")
    raw = path.read_bytes()
    try:
        source = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid subject exception source") from error
    if source.get("ego_id") != ego_id:
        raise ValueError("Subject exception source actor identity differs")
    for premise, context_key, filename in (
        ("authorized_emergency", "subject_authorized_emergency", "authorization.json"),
        ("official_business", "subject_official_business", "official_business.json"),
    ):
        item = source.get(premise)
        if not isinstance(item, dict) or type(item.get("asserted")) is not bool:
            raise ValueError("Subject exception premise needs an explicit assertion: " + premise)
        if item["asserted"] is not context[context_key]:
            raise ValueError("Subject exception premise conflicts with capture context: " + premise)
        relative = "source_packets/" + filename
        if item.get("packet") != relative or not isinstance(item.get("packet_sha256"), str):
            raise ValueError("Subject exception premise lacks packet binding: " + premise)
        packet_path = root / relative
        if not packet_path.is_file():
            raise ValueError("Missing required source: " + relative)
        packet_raw = packet_path.read_bytes()
        if sha256(packet_raw).hexdigest() != item["packet_sha256"]:
            raise ValueError("Original exception packet hash differs: " + premise)
        try:
            packet = json.loads(packet_raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Invalid original exception packet: " + premise) from error
        if (packet.get("ego_id") != ego_id or packet.get("asserted") is not item["asserted"]
                or not isinstance(packet.get("source_ref"), str)
                or not packet["source_ref"].strip()
                or packet["source_ref"] != item.get("source_ref")):
            raise ValueError("Original exception packet assertion differs: " + premise)
    return {"value": source, "sha256": sha256(raw).hexdigest()}
