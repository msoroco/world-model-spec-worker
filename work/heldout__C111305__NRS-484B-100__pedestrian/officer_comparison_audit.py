"""Independent CPU comparison of retained officer-response measurements."""
from __future__ import annotations
import json
from pathlib import Path

def audit(measurements, *, expected_actor, expected_command, fixed_subject_id, fixed_officer_id):
    if len(measurements) != 2:
        raise ValueError("comparison requires two exact cases")
    rows = [json.loads(Path(p).read_text()) for p in measurements]
    for r in rows:
        if r.get("actor_role") != expected_actor or r.get("command") != expected_command:
            raise ValueError("fixed actor or indication changed")
        if r.get("subject_id") != fixed_subject_id or r.get("officer_id") != fixed_officer_id:
            raise ValueError("fixed subject or officer changed")
        if r.get("legal_conclusion") is not None or r.get("willfulness_conclusion") is not None:
            raise ValueError("measurement asserts prohibited legal conclusion")
        if r.get("post_indication_samples", 0) < 2 or len(r.get("source_refs", [])) != 3:
            raise ValueError("missing source-bound post-indication evidence")
    responses = [r.get("observed_response") for r in rows]
    allowed = {"stop": {"stopped_after_indication", "no_observed_stop"},
               "proceed": {"moved_after_indication", "no_observed_movement"}}[expected_command]
    if set(responses) != allowed:
        raise ValueError("comparison did not isolate distinct observed responses")
    return {"comparison_complete": True, "fixed_conditions_checked": ["actor_role","command","subject_id","officer_id"],
            "deliberate_difference": "observed post-indication motion", "responses": responses,
            "legal_conclusion": None}
