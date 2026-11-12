"""Decode all four selected diagnostic sources through the delivery RGB checker.

This proves byte/frame plumbing only. Synthetic pixels cannot prove physical sight.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from delivery_audit import CAMERAS, check_rgb_frame, rows, sha
from scenario_pipeline.worker_exchange.media import audit as decode

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ATTEMPT = ROOT/".runtime-work/c104538-final-below-primary-compat"
DECODE = (ROOT/".runtime-work/c104538-update021-delivery-media"/
          sha(HERE/"delivery_audit.py"))


def run() -> dict:
    provenance = json.loads((ATTEMPT/"acquisition-provenance.json").read_text())
    assert provenance.get("diagnostic_fixture") is True
    assert provenance.get("provenance_kind") != "native"
    mapping = rows(ATTEMPT/"video_frames.jsonl")
    assert len(mapping) == 480
    DECODE.mkdir(parents=True, exist_ok=True)
    receipts = {}
    for camera in CAMERAS:
        def check(frame, camera=camera):
            check_rgb_frame(frame, mapping, camera)
        path = DECODE/(camera + ".json")
        result = decode(ATTEMPT/(camera + ".mkv"), 480,
                        mapping_sha256=sha(ATTEMPT/"video_frames.jsonl"),
                        checkers={"original_rgb_sha256": (sha(HERE/"delivery_audit.py"), check)},
                        receipt=path)
        assert result["passed"] is True and result["frames"] == 480
        assert result["checks"]["original_rgb_sha256"] == sha(HERE/"delivery_audit.py")
        receipts[camera] = {"video_sha256": result["video_sha256"],
                            "decode_receipt_sha256": sha(path),
                            "rgb_sequence_sha256": result["rgb_sequence_sha256"]}
    report = {"format": "c104538-diagnostic-delivery-media-proof-v1",
              "case_id": HERE.name + "__below_500_ft",
              "source_shaped_unit_test": True,
              "all_four_source_cameras_decoded": True,
              "frames_per_camera": 480,
              "source_frame_map_sha256": sha(ATTEMPT/"video_frames.jsonl"),
              "camera_receipts": receipts,
              "original_native_pixels_proven": False,
              "original_500_foot_visibility_proven": False,
              "legal_verdict_claimed": False}
    path = HERE/"update021-delivery-media-proof.json"
    path.write_text(json.dumps(report, indent=2)+"\n")
    return {"camera_count": len(receipts), "frames_per_camera": 480,
            "proof_sha256": sha(path), "original_native_pixels_proven": False}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
