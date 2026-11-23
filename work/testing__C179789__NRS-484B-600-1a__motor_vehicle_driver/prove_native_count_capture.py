"""Verify a sealed original Native count history before judgment-range use."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from native_count_probes import KINDS


def prove(source: Path, *, case_id: str, kind: str, packet_sha256: str,
          opendrive_sha256: str, declared_blueprint_ids: list[str]) -> dict:
    source = Path(source)
    seal = source.with_name(source.name + ".seal.json")
    raw = source.read_bytes()
    receipt = json.loads(seal.read_text(encoding="utf-8"))
    if (kind not in KINDS or receipt.get("format") != "c179789-original-count-source-v1" or
            receipt.get("case_id") != case_id or receipt.get("kind") != kind or
            receipt.get("sample_count") != 900 or
            receipt.get("sha256") != hashlib.sha256(raw).hexdigest() or
            receipt.get("physical_acceptance_claimed") is not False):
        raise ValueError("original count source seal mismatch")
    rows = [json.loads(line) for line in raw.splitlines()]
    if len(rows) != 900 or not case_id or not packet_sha256 or not opendrive_sha256:
        raise ValueError("original count history incomplete")
    first_frame = rows[0].get("native_frame")
    first_ids = rows[0].get("actor_ids")
    if type(first_frame) is not int or not isinstance(first_ids, list):
        raise ValueError("original count frame or identities invalid")
    previous_time = -math.inf
    for index, row in enumerate(rows):
        observed = row.get("actors")
        identities = row.get("actor_ids")
        elapsed = row.get("native_elapsed_s")
        if (row.get("case_id") != case_id or row.get("kind") != kind or
                row.get("packet_sha256") != packet_sha256 or
                row.get("opendrive_sha256") != opendrive_sha256 or
                row.get("native_frame") != first_frame + index or
                type(elapsed) not in (int, float) or not math.isfinite(elapsed) or
                elapsed <= previous_time or identities != first_ids or
                not isinstance(observed, list) or len(observed) != len(declared_blueprint_ids) or
                len(identities) != len(observed) or len(set(identities)) != len(identities)):
            raise ValueError("original count row continuity or source mismatch")
        if index and abs((elapsed - previous_time) - .05) > .001:
            raise ValueError("original count sample rate differs from 20 Hz")
        for actor, actor_id, blueprint in zip(observed, identities, declared_blueprint_ids):
            if (type(actor_id) is not int or actor.get("actor_id") != actor_id or
                    actor.get("type_id") != blueprint or type(actor.get("alive")) is not bool):
                raise ValueError("original count actor readback mismatch")
        if row.get("observed_count") != sum(actor["alive"] for actor in observed):
            raise ValueError("original count was not measured from readback")
        previous_time = elapsed
    return {"format": "c179789-original-count-proof-v1", "case_id": case_id,
            "kind": kind, "sample_count": 900, "first_observed_count": rows[0]["observed_count"],
            "minimum_observed_count": min(row["observed_count"] for row in rows),
            "maximum_observed_count": max(row["observed_count"] for row in rows),
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "physical_acceptance_claimed": False}
