"""Independent 30-second source-shaped CPU tests of C111071 timing component."""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from cycle_controller import EGO_FACE, FRAMES, Sample, commanded_brake, measure


HERE = Path(__file__).resolve().parent


def fixture(entry: int) -> list[Sample]:
    out = []
    for f in range(FRAMES):
        # 120-frame complete device cycles. The initial phase at stop frame 20
        # reappears only after the other two phases at frames 120 and 240.
        phase = ("cross_green", "cross_yellow", "cross_red")[(f % 120) // 40]
        out.append(Sample(f, EGO_FACE, phase, 0.0 if 15 <= f < entry else 3.0,
                          4.0 if f < entry else -1.0, f >= entry, True, False,
                          False, False))
    return out


def proof() -> dict:
    positive = fixture(250)
    early = fixture(130)
    p = measure(positive)
    n = measure(early)
    assert p["requested_gate_satisfied"] and p["complete_cycle_end_frames"][:2] == [120, 240]
    assert not n["requested_gate_satisfied"] and not n["two_cycles_before_entry"]
    assert commanded_brake(positive[100], 0, 2) == 1.0
    assert commanded_brake(positive[241], 2, 2) == 0.0
    negatives = {}
    mutations = {
        "missing_frame": positive[:-1],
        "changed_ego_arrow": [replace(s, ego_face="circular_red") if s.frame == 100 else s for s in positive],
        "no_halt": [replace(s, ego_speed_mps=2.0) if 15 <= s.frame < 250 else s for s in positive],
        "detector_serviced": [replace(s, detector_request_serviced=True) if s.frame == 150 else s for s in positive],
        "pedestrian_conflict": [replace(s, pedestrians_in_crosswalk=True) if s.frame == 250 else s for s in positive],
        "duplicate_frame": [replace(s, frame=19) if s.frame == 20 else s for s in positive],
    }
    for name, altered in mutations.items():
        try:
            result = measure(altered)
            negatives[name] = not result["requested_gate_satisfied"]
        except ValueError:
            negatives[name] = True
    assert all(negatives.values()), negatives
    source = HERE / "cycle_controller.py"
    return {
        "format": "c111071-cycle-controller-cpu-proof-v1",
        "assignment_id": "training__C111071__NRS-484B-307-9b__motorcycle_or_moped_operator",
        "controller_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "positive": p,
        "controlled_early_entry": n,
        "negative_mutations_rejected": negatives,
        "source_kind": "synthetic_native_sample",
        "native_observation": False,
        "physical_or_legal_acceptance": False,
    }


if __name__ == "__main__":
    result = proof()
    path = HERE / "cycle-controller-proof.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"proof": str(path), "positive": result["positive"]["requested_gate_satisfied"],
                      "negative_count": len(result["negative_mutations_rejected"])}, sort_keys=True))
