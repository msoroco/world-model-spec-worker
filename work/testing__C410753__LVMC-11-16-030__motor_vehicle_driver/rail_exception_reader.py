"""Source-gated original flagman duty and crossing signal readbacks.

The reader rejects missing authority/designation or missing original per-frame
source. A present actor or light blueprint alone never proves an exception.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

FIELDS = ("flagman_on_duty", "signal_installed", "signal_clearly_visible",
          "signal_immediate_train_approach")


class ReviewedRailExceptionReader:
    def __init__(self, site, source_path, attempt_root, original_reader):
        raw = Path(source_path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != site.get("rail_exception_review_sha256"):
            raise ValueError("reviewed railway exception source hash differs")
        review = json.loads(raw)
        if (review.get("source_kind") != "railway_exception_review" or
                not review.get("reviewer") or not review.get("source_citation") or
                review.get("road_sha256") != site.get("road_sha256") or
                not review.get("flagman_duty_authority_source") or
                not review.get("signal_installation_source") or
                review.get("signal_kind") not in ("electrical", "mechanical")):
            raise ValueError("reviewed railway exception authority incomplete")
        if not callable(original_reader):
            raise ValueError("original railway exception reader missing")
        self.root = Path(attempt_root).resolve()
        self.original_reader = original_reader
        self.last_frame = None

    def __call__(self, frame, snapshot, ego):
        if (type(frame) is not int or snapshot.frame != frame or
                (self.last_frame is not None and frame != self.last_frame + 1)):
            raise ValueError("original railway exception frame join differs")
        readback = self.original_reader(frame, snapshot, ego)
        if not isinstance(readback, dict) or any(
                type(readback.get(key)) is not bool for key in FIELDS):
            raise ValueError("original railway exception state missing")
        ref = readback.get("original_source")
        if not isinstance(ref, dict):
            raise ValueError("original railway exception source missing")
        relative = Path(ref.get("path", ""))
        source = (self.root / relative).resolve()
        if (relative.is_absolute() or ".." in relative.parts or
                not source.is_relative_to(self.root) or not source.is_file() or
                source.is_symlink() or
                hashlib.sha256(source.read_bytes()).hexdigest() != ref.get("sha256")):
            raise ValueError("original railway exception source missing or changed")
        original = json.loads(source.read_text())
        if original.get("frame") != frame or any(
                original.get(key) != readback[key] for key in FIELDS):
            raise ValueError("original railway exception readback differs")
        self.last_frame = frame
        return {key: readback[key] for key in FIELDS} | {"source_trace": ref}
