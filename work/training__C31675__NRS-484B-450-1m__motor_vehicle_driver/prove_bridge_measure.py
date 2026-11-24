"""Synthetic source-shaped CPU checks for bridge spatial measurement."""
from __future__ import annotations

import hashlib
import json
from bridge_measure import measure


BRIDGE = json.dumps({"structure_type": "bridge", "deck_polygon_xy_m":
                     [[0, 0], [20, 0], [20, 8], [0, 8]]}).encode()


def trace(x: float, speed: float = 0.0) -> bytes:
    rows = [{"frame": i, "time_s": i / 20, "speed_mps": speed,
             "body_footprint_xy_m": [[x, 2], [x+4, 2], [x+4, 4], [x, 4]]}
            for i in range(3)]
    return ("\n".join(json.dumps(r) for r in rows) + "\n").encode()


def run(source: bytes, bridge: bytes = BRIDGE) -> dict:
    return measure(source, bridge, trace_sha256=hashlib.sha256(source).hexdigest(),
                   bridge_sha256=hashlib.sha256(bridge).hexdigest())


def reject(source: bytes, bridge: bytes, reason: str) -> None:
    try:
        run(source, bridge)
    except ValueError as error:
        assert reason in str(error), error
    else:
        raise AssertionError("invalid source passed: " + reason)


def main() -> None:
    observed = {name: run(trace(x))["rows"][0]["bridge_relation"]
                for name, x in (("full", 5), ("partial", -2), ("none", -5))}
    assert observed == {"full": "full", "partial": "partial", "none": "none"}
    moving = run(trace(5, speed=1))["rows"]
    assert all(not row["stationary_candidate"] for row in moving)
    assert all(row["stationary_candidate"] for row in run(trace(5))["rows"])
    sample = trace(5)
    try:
        measure(sample, BRIDGE, trace_sha256="0"*64,
                bridge_sha256=hashlib.sha256(BRIDGE).hexdigest())
    except ValueError as error:
        assert "hash mismatch" in str(error)
    else:
        raise AssertionError("tampered hash accepted")
    reject(sample, json.dumps({"structure_type": "tunnel", "deck_polygon_xy_m":
                               [[0, 0], [20, 0], [20, 8], [0, 8]]}).encode(), "not a bridge")
    bad = json.loads(sample.splitlines()[1]); bad["frame"] = 2
    reject(sample.splitlines()[0]+b"\n"+json.dumps(bad).encode()+b"\n"+sample.splitlines()[2]+b"\n",
           BRIDGE, "saved frame")
    bad = json.loads(sample.splitlines()[1]); bad["speed_mps"] = None
    reject(sample.splitlines()[0]+b"\n"+json.dumps(bad).encode()+b"\n"+sample.splitlines()[2]+b"\n",
           BRIDGE, "observed speed")
    print(json.dumps({"format": "c31675-bridge-measure-cpu-proof-v1", "passed": True,
                      "source_kind": "synthetic_native_sample", "relations": observed,
                      "moving_control": True, "negative_source_probes": 4,
                      "original_native_or_legal_result": None}, sort_keys=True))


if __name__ == "__main__":
    main()
