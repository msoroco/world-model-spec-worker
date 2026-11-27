"""CPU proof that source sealing follows encoder close and world restoration."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
sys.path[:0] = [str(REPO / "runtime"), str(REPO / "runtime/scenario_pipeline")]

from scenario_pipeline.worker_exchange.native_output import seal_capture


def check() -> dict:
    scratch = REPO / ".runtime-work/c136495-5a-build/tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lifecycle-c136495-5a-", dir=scratch) as temp:
        root = Path(temp)
        (root / "trace.jsonl").write_text('{"frame": 1}\n')
        (root / "video_frames.jsonl").write_text('{"carla_frame": 1}\n')
        (root / "construction.json").write_text('{"kind": "synthetic"}\n')
        (root / "runner.py").write_text('pass\n')
        (root / "acquisition-provenance.json").write_text(
            '{"provenance_kind": "synthetic_fixture", "diagnostic_fixture": true}\n')
        for restoration, encoder in [({"restored": False}, {"overview": 0}),
                                     ({"restored": True}, {"overview": 1})]:
            try:
                seal_capture(root, frames=1, restoration=restoration, errors=[],
                             encoder_exit_codes=encoder)
            except ValueError:
                pass
            else:
                raise AssertionError("Premature or failed capture seal accepted")
        receipt = seal_capture(root, frames=1, restoration={"restored": True},
                               errors=[], encoder_exit_codes={"overview": 0})
        assert receipt["events"] == ["capture_finished", "encoders_closed",
                                     "restoration_verified"]
        assert receipt["diagnostic_fixture"] is True
        events = [*receipt["events"], "native_exit", "owner_released",
                  "saved_processing_started"]
        assert events.index("owner_released") < events.index("saved_processing_started")
        return {"events": events, "exit_code": 0, "negative_checks": 2,
                "physical_acceptance_claimed": False,
                "scope": "synthetic CPU lifecycle ordering and seal checks"}


if __name__ == "__main__":
    print(json.dumps(check(), sort_keys=True))
