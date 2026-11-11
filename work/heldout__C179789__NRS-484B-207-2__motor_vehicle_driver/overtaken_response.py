"""Measured overtaken-driver response; source context is not a legal decision."""
from __future__ import annotations
import json
from pathlib import Path


def _read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"missing required original source: {path}")
    return json.loads(path.read_text())


def measure(context_path, events_path, motion_path):
    context, events, motion = map(_read, (context_path, events_path, motion_path))
    if not context.get("road_source") or not context.get("actor_source"):
        raise ValueError("road and actor context source references required")
    if context.get("right_pass_permitted") not in (True, False) or not context.get("right_pass_permission_source"):
        raise ValueError("right-pass exception needs explicit sourced premise")
    if context.get("legal_conclusion") is not None:
        raise ValueError("fixture cannot assert a legal conclusion")
    subject, overtaker = context.get("subject_id"), context.get("overtaker_id")
    if not subject or not overtaker or subject == overtaker:
        raise ValueError("distinct subject and overtaker identities required")
    notice = events.get("notice_frame")
    complete = events.get("pass_complete_frame")
    if type(notice) is not int or type(complete) is not int or not 0 <= notice < complete:
        raise ValueError("notice and pass completion order missing")
    if events.get("notice_kind") not in ("observed", "audible_signal") or not events.get("notice_source"):
        raise ValueError("observed or heard passing notice source missing")
    if events.get("subject_id") != subject or events.get("overtaker_id") != overtaker:
        raise ValueError("event actor identities differ")
    rows = motion.get("frames")
    if not isinstance(rows, list) or len(rows) < 3:
        raise ValueError("retained original motion span missing")
    frames = [r.get("frame") for r in rows]
    if any(type(x) is not int for x in frames) or frames != sorted(set(frames)):
        raise ValueError("original motion frames unordered or repeated")
    if not (frames[0] <= notice < complete <= frames[-1]):
        raise ValueError("motion does not bracket notice and pass completion")
    if any(r.get("subject_id") != subject or r.get("overtaker_id") != overtaker for r in rows):
        raise ValueError("motion actor identities differ")
    if any(type(r.get("speed_mps")) not in (int, float) or r["speed_mps"] < 0 or
           type(r.get("right_offset_m")) not in (int, float) for r in rows):
        raise ValueError("original speed or right offset missing")
    before = [r for r in rows if r["frame"] <= notice]
    during = [r for r in rows if notice < r["frame"] < complete]
    if not during:
        raise ValueError("no motion samples before passing is complete")
    at_notice = before[-1]
    max_right_shift = max(r["right_offset_m"] - at_notice["right_offset_m"] for r in during)
    max_speed_delta = max(r["speed_mps"] - at_notice["speed_mps"] for r in during)
    return {"subject_id": subject, "overtaker_id": overtaker,
            "right_pass_permitted_premise": context["right_pass_permitted"],
            "notice_kind": events["notice_kind"], "notice_frame": notice,
            "pass_complete_frame": complete, "max_right_shift_m": max_right_shift,
            "max_precompletion_speed_delta_mps": max_speed_delta,
            "source_refs": [str(context_path), str(events_path), str(motion_path)],
            "legal_conclusion": None}


def main():
    import argparse
    p = argparse.ArgumentParser()
    for key in ("context", "events", "motion", "output"):
        p.add_argument("--" + key, required=True)
    a = p.parse_args()
    Path(a.output).write_text(json.dumps(measure(a.context, a.events, a.motion), indent=2) + "\n")


if __name__ == "__main__":
    main()
