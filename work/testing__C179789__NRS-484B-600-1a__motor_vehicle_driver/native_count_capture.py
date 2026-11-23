"""Write-once full-episode original Native actor-count history.

The recorder is called from the Native tick loop; fake readers in CPU tests
exercise joins only. A count target is never inferred from the spawn request.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from native_count_probes import KINDS


class CountCapture:
    def __init__(self, construction: dict):
        if construction.get("kind") not in KINDS or not construction.get("case_id"):
            raise ValueError("exact count construction missing")
        actors = construction.get("actors")
        if not isinstance(actors, list) or len(actors) != construction.get("expected_count"):
            raise ValueError("constructed count actor inventory differs")
        if (not isinstance(construction.get("declared_blueprint_ids"), list) or
                len(construction["declared_blueprint_ids"]) != len(actors)):
            raise ValueError("declared count actor blueprints missing")
        if not construction.get("packet_sha256") or not construction.get("opendrive_sha256"):
            raise ValueError("count construction source missing")
        self.construction = construction
        self.rows = []
        self.closed = False

    def append(self, snapshot, actor_reader):
        if self.closed:
            raise ValueError("count source already closed")
        frame = snapshot.frame
        elapsed = snapshot.timestamp.elapsed_seconds
        if type(frame) is not int or frame < 0 or not math.isfinite(elapsed):
            raise ValueError("invalid original Native frame/time")
        if self.rows and (frame != self.rows[-1]["native_frame"] + 1 or
                          abs((elapsed - self.rows[-1]["native_elapsed_s"]) - .05) > .001):
            raise ValueError("count original frame/time discontinuity")
        identities = []
        observed = []
        for actor, blueprint_id in zip(self.construction["actors"],
                                       self.construction["declared_blueprint_ids"]):
            sample = actor_reader(actor)
            if (not isinstance(sample, dict) or type(sample.get("actor_id")) is not int or
                    not isinstance(sample.get("type_id"), str) or not sample["type_id"] or
                    type(sample.get("alive")) is not bool):
                raise ValueError("original count actor readback missing")
            if sample["type_id"] != blueprint_id:
                raise ValueError("original count actor blueprint differs")
            if sample["actor_id"] in identities:
                raise ValueError("duplicate original count actor")
            identities.append(sample["actor_id"])
            observed.append(sample)
        if self.rows and identities != self.rows[0]["actor_ids"]:
            raise ValueError("original count actor identity changed")
        row = {"case_id": self.construction["case_id"], "kind": self.construction["kind"],
               "native_frame": frame, "native_elapsed_s": elapsed,
               "actor_ids": identities, "actors": observed,
               "observed_count": sum(item["alive"] for item in observed),
               "packet_sha256": self.construction["packet_sha256"],
               "opendrive_sha256": self.construction["opendrive_sha256"]}
        self.rows.append(row)
        return row

    def close(self, output: Path):
        if self.closed or len(self.rows) != 900:
            raise ValueError("count source requires one complete 900-frame episode")
        output = Path(output)
        seal = output.with_name(output.name + ".seal.json")
        if output.exists() or seal.exists():
            raise ValueError("original count source already exists")
        data = "".join(json.dumps(row, sort_keys=True) + "\n" for row in self.rows).encode()
        output.write_bytes(data)
        receipt = {"format": "c179789-original-count-source-v1",
                   "case_id": self.construction["case_id"],
                   "kind": self.construction["kind"], "sample_count": len(self.rows),
                   "sha256": hashlib.sha256(data).hexdigest(),
                   "physical_acceptance_claimed": False}
        seal.write_text(json.dumps(receipt, indent=2) + "\n")
        self.closed = True
        return receipt
