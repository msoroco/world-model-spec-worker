"""Exercise each planned observation contrast without assigning a legal hazard cutoff."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(PACKAGE))
from tests.test_yield_entry import YieldEntryTests, body
from yield_entry_measurements import analyze

KINDS = ("yield_other_inside", "yield_other_approaching", "yield_other_obligated",
         "yield_no_slow", "officer_control_exception")
PREFIX = "testing__C158208__NRS-484B-257-2__motor_vehicle_driver__"


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def make(root, kind):
    YieldEntryTests().fixture(root, "stop" if kind == "yield_other_obligated" else "none")
    context = json.loads((root / "intersection_context.json").read_text())
    context["case_id"] = PREFIX + kind
    context["police_control"] = kind == "officer_control_exception"
    write(root / "intersection_context.json", context)
    review = json.loads((root / "site_review.json").read_text())
    review["intersection_context_sha256"] = hashlib.sha256(
        (root / "intersection_context.json").read_bytes()).hexdigest()
    write(root / "site_review.json", review)
    rows = [json.loads(line) for line in (root / "entry_history.jsonl").read_text().splitlines()]
    if kind == "yield_other_approaching":
        for row, x in zip(rows, (35, 30, 25)):
            row["other_body_vertices_xy_m"] = body(x)
    if kind == "yield_no_slow":
        for row in rows:
            row["ego_speed_mps"] = 4
    (root / "entry_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    if kind == "officer_control_exception":
        write(root / "officer_review.json", {
            "intersection_context_sha256": review["intersection_context_sha256"],
            "camera_sha256": review["camera_sha256"],
            "reviewed_carla_frames": [100, 101, 102], "officer_actor_id": 99,
            "control_observed_at_entry": True, "authority_judgment": "unresolved"})


def main():
    expected = {
        "yield_other_inside": (True, True, True),
        "yield_other_approaching": (False, True, True),
        "yield_other_obligated": (True, False, True),
        "yield_no_slow": (True, True, False),
        "officer_control_exception": (True, True, True),
    }
    output = []
    scratch = ROOT / ".runtime-work"
    scratch.mkdir(exist_ok=True)
    for kind in KINDS:
        with tempfile.TemporaryDirectory(dir=scratch, prefix="c158208-judgment-") as folder:
            root = Path(folder)
            make(root, kind)
            observed = analyze(root)
            values = (observed["other_inside_at_ego_entry"],
                      observed["other_not_obligated_by_stop_or_yield"],
                      observed["observed_slowed_or_stopped_before_reference"])
            if values != expected[kind]:
                raise ValueError("Exact-case judgment sweep differs: " + kind + ": " + str(values))
            if (kind == "yield_other_approaching"
                    and observed["samples"][-1]["other_center_closing_mps"] <= 0):
                raise ValueError("Approaching source lacks measured closing motion")
            if observed["officer_control_observed"] != (kind == "officer_control_exception"):
                raise ValueError("Officer observation differs from exact source review")
            if (observed["immediate_hazard_judgment"] != "unresolved"
                    or observed["caution_and_yield_judgment"] != "unresolved"
                    or observed["legal_conclusion"] != "unresolved"):
                raise ValueError("Diagnostic assigned a legal judgment")
            output.append({"case_id": PREFIX + kind, "observations": values,
                           "immediate_hazard_judgment": "unresolved",
                           "legal_conclusion": "unresolved", "diagnostic_fixture": True})
    print(json.dumps({"format": "c158208-exact-judgment-cpu-sweep", "cases": output},
                     sort_keys=True))


if __name__ == "__main__":
    main()
