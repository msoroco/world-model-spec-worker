"""Check source-bound comparison isolation for overtaken-driver diagnostics."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def audit(result_paths, comparison):
    if comparison not in ("right_shift", "speed_hold_until_complete", "right_pass_exception", "notice_modality"):
        raise ValueError("Unsupported overtaken-driver comparison")
    if len(result_paths) != 2:
        raise ValueError("Exactly two retained result paths are required")
    first, second = (json.loads(Path(path).read_text()) for path in result_paths)
    for result in (first, second):
        hashes = result.get("source_sha256")
        if not isinstance(hashes, dict) or not all(hashes.get(key) for key in ("context", "events", "motion")):
            raise ValueError("Comparison lacks original source binding")
        paths = result.get("source_paths")
        if not isinstance(paths, dict) or not all(paths.get(key) for key in ("context", "events", "motion")):
            raise ValueError("Comparison lacks original source paths")
        for key in ("context", "events", "motion"):
            if hashlib.sha256(Path(paths[key]).read_bytes()).hexdigest() != hashes[key]:
                raise ValueError("Comparison original source changed: "+key)
        if result.get("legal_conclusion") is not None:
            raise ValueError("Diagnostic comparison cannot assert a legal conclusion")
    fixed = ("subject_id", "overtaker_id", "notice_frame", "pass_complete_frame",
             "road_source", "actor_source")
    if comparison != "notice_modality":
        fixed += ("notice_kind", "notice_source")
    if any(first.get(key) != second.get(key) for key in fixed):
        raise ValueError("Comparison changed held notice or actor conditions")
    if comparison == "right_shift":
        if first.get("right_pass_permitted_premise") != second.get("right_pass_permitted_premise"):
            raise ValueError("Right-shift comparison changed held exception premise")
        if first.get("max_precompletion_speed_delta_mps") != second.get("max_precompletion_speed_delta_mps"):
            raise ValueError("Right-shift comparison changed held motion")
        varied = "max_right_shift_m"
    elif comparison == "speed_hold_until_complete":
        if first.get("right_pass_permitted_premise") != second.get("right_pass_permitted_premise") or first.get("max_right_shift_m") != second.get("max_right_shift_m"):
            raise ValueError("Speed comparison changed held motion or exception premise")
        varied = "max_precompletion_speed_delta_mps"
    elif comparison == "right_pass_exception":
        if first.get("max_precompletion_speed_delta_mps") != second.get("max_precompletion_speed_delta_mps") or first.get("max_right_shift_m") != second.get("max_right_shift_m"):
            raise ValueError("Exception comparison changed held motion")
        varied = "right_pass_permitted_premise"
    else:
        if (first.get("right_pass_permitted_premise") != second.get("right_pass_permitted_premise")
                or first.get("max_precompletion_speed_delta_mps") != second.get("max_precompletion_speed_delta_mps")
                or first.get("max_right_shift_m") != second.get("max_right_shift_m")):
            raise ValueError("Notice comparison changed held motion or exception premise")
        varied = "notice_kind"
    if first.get(varied) == second.get(varied):
        raise ValueError("Comparison has no declared difference")
    return {"comparison_complete": True, "comparison": comparison, "declared_difference": varied,
            "source_hashes": [first["source_sha256"], second["source_sha256"]],
            "legal_conclusion": None}
