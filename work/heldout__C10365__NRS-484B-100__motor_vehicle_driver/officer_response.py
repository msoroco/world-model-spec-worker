"""Source-bound observation of response to an officer's timed direction.

This records motion only. Officer authority, lawful order and willfulness remain
independent source and legal review questions.
"""
from __future__ import annotations
import json
from pathlib import Path


def _load(path):
    p = Path(path)
    if not p.is_file():
        raise ValueError("missing required source: " + str(p))
    return json.loads(p.read_text())


def measure(context_path, direction_path, motion_path, *, expected_actor, expected_command):
    context, direction, motion = (_load(p) for p in (context_path, direction_path, motion_path))
    if context.get("actor_role") != expected_actor:
        raise ValueError("actor role differs from exact case")
    if context.get("officer_role") != "police_officer" or not context.get("officer_id"):
        raise ValueError("officer role or identity missing")
    if not context.get("duty_source") or not context.get("lawfulness_source"):
        raise ValueError("officer duty and order-lawfulness source references required")
    if context.get("legal_conclusion") or context.get("willfulness_conclusion"):
        raise ValueError("fixture may not assert legal or willfulness conclusion")
    if direction.get("officer_id") != context["officer_id"] or direction.get("subject_id") != context.get("subject_id"):
        raise ValueError("direction is not source-bound to this officer and subject")
    if direction.get("command") != expected_command or expected_command not in ("stop", "proceed"):
        raise ValueError("direction differs from exact case")
    frame = direction.get("frame")
    if type(frame) is not int or frame < 0 or not direction.get("indication_source"):
        raise ValueError("timed officer indication source missing")
    rows = motion.get("frames")
    if not isinstance(rows, list) or len(rows) < 3:
        raise ValueError("retained subject motion span missing")
    indices = [r.get("frame") for r in rows]
    if any(type(i) is not int for i in indices) or indices != sorted(set(indices)):
        raise ValueError("motion frame identities must be unique and ordered")
    if not (indices[0] <= frame < indices[-1]):
        raise ValueError("motion does not bracket direction and response")
    if any(r.get("subject_id") != context["subject_id"] for r in rows):
        raise ValueError("motion subject differs from direction subject")
    if any(type(r.get("speed_mps")) not in (int, float) or r["speed_mps"] < 0 for r in rows):
        raise ValueError("invalid original subject speed sample")
    following = [r for r in rows if r["frame"] > frame]
    if len(following) < 2:
        raise ValueError("at least two post-indication motion samples required")
    # Descriptive engineering observation, not a legal compliance threshold.
    stopped = any(r["speed_mps"] <= 0.1 for r in following)
    moving = any(r["speed_mps"] > 0.5 for r in following)
    if expected_command == "stop":
        response = "stopped_after_indication" if stopped else "no_observed_stop"
    else:
        response = "moved_after_indication" if moving else "no_observed_movement"
    return {"actor_role": expected_actor, "subject_id": context["subject_id"],
            "officer_id": context["officer_id"], "command": expected_command,
            "indication_frame": frame, "first_motion_frame": indices[0],
            "last_motion_frame": indices[-1], "post_indication_samples": len(following),
            "min_post_speed_mps": min(r["speed_mps"] for r in following),
            "max_post_speed_mps": max(r["speed_mps"] for r in following),
            "observed_response": response,
            "source_refs": [str(context_path), str(direction_path), str(motion_path)],
            "legal_conclusion": None, "willfulness_conclusion": None}


def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--context",required=True)
    ap.add_argument("--direction",required=True)
    ap.add_argument("--motion",required=True)
    ap.add_argument("--actor",required=True)
    ap.add_argument("--command",choices=("stop","proceed"),required=True)
    ap.add_argument("--output",required=True)
    a=ap.parse_args()
    result=measure(a.context,a.direction,a.motion,expected_actor=a.actor,expected_command=a.command)
    Path(a.output).write_text(json.dumps(result,indent=2)+"\n")
if __name__ == "__main__": main()
