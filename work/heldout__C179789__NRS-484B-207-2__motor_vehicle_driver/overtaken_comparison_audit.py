"""Independent fixed-condition audit for overtaken-driver comparisons."""
import json
from pathlib import Path


def audit(paths, variable):
    if variable not in ("right_shift", "speed_change", "right_pass_exception") or len(paths) != 2:
        raise ValueError("exact two-case comparison and known variable required")
    a, b = [json.loads(Path(p).read_text()) for p in paths]
    for row in (a, b):
        if len(row.get("source_refs", [])) != 3 or row.get("legal_conclusion") is not None:
            raise ValueError("source-bound measurement missing or legal conclusion asserted")
    for key in ("subject_id", "overtaker_id", "notice_kind"):
        if a.get(key) != b.get(key):
            raise ValueError("fixed actor or notice condition changed: " + key)
    if variable == "right_shift":
        fixed, varied = "max_precompletion_speed_delta_mps", "max_right_shift_m"
    elif variable == "speed_change":
        fixed, varied = "max_right_shift_m", "max_precompletion_speed_delta_mps"
    else:
        fixed, varied = "max_precompletion_speed_delta_mps", "right_pass_permitted_premise"
        if abs(a.get("max_right_shift_m", 0) - b.get("max_right_shift_m", 0)) > 0.001:
            raise ValueError("held lateral path changed")
    if a.get(fixed) != b.get(fixed):
        raise ValueError("held motion variable changed: " + fixed)
    if a.get(varied) == b.get(varied):
        raise ValueError("deliberate comparison variable did not change")
    if variable != "right_pass_exception" and a.get("right_pass_permitted_premise") != b.get("right_pass_permitted_premise"):
        raise ValueError("right-pass permission premise changed")
    return {"comparison_complete": True, "variable": variable,
            "fixed_conditions_checked": ["subject_id", "overtaker_id", "notice_kind", fixed],
            "legal_conclusion": None}
