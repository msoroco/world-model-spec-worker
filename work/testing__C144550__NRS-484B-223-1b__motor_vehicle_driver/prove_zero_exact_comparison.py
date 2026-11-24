"""Audit exact synthetic zero/late candidates as a controlled lamp comparison."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCES = HERE / "diagnostic-sources"
OLD = HERE / "cases/left_signal_late_clear_gap/diagnostic.json"
NEW = HERE / "cases/left_signal_at_departure_clear_gap/diagnostic.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(name):
    return [json.loads(line) for line in (SOURCES / name).read_text().splitlines()]


def compare():
    names = (("lane_history", "late-lane_history.jsonl", "zero-lane_history.jsonl"),
             ("trace", "late-trace.jsonl", "zero-trace.jsonl"),
             ("capture", "late-capture-evidence.jsonl", "zero-capture-evidence.jsonl"))
    changed = {}
    for kind, before, after in names:
        old, new = rows(before), rows(after)
        if len(old) != len(new) or len(new) != 900:
            raise ValueError("Incomplete fixed 900-frame comparison: " + kind)
        differences = [i for i, (a, b) in enumerate(zip(old, new)) if a != b]
        if differences != [1]:
            raise ValueError("Comparison changed a nondeparture frame: " + kind)
        a, b = old[1], new[1]
        if a.get("original_frame", a.get("frame")) != 101 or b.get("original_frame", b.get("frame")) != 101:
            raise ValueError("Comparison departure frame changed")
        if kind == "lane_history":
            if (a.pop("indicator"), b.pop("indicator")) != ("off", "left"):
                raise ValueError("Lane-history lamp difference changed")
        elif kind == "trace":
            if (a.pop("ego_lamp_bits"), b.pop("ego_lamp_bits")) != (0, 32):
                raise ValueError("Trace lamp difference changed")
        else:
            x = a["original_observations"]["participants"][0].pop("light_attributes")
            y = b["original_observations"]["participants"][0].pop("light_attributes")
            if (x, y) != ({"light_LeftBlinker":False,"light_RightBlinker":False},
                          {"light_LeftBlinker":True,"light_RightBlinker":False}):
                raise ValueError("Capture lamp difference changed")
        if a != b:
            raise ValueError("Nonlamp source fields changed: " + kind)
        changed[kind] = {"baseline_sha256":sha(SOURCES / before),
                         "zero_sha256":sha(SOURCES / after),"changed_frame":101}

    prior = json.loads(OLD.read_text())
    new = json.loads(NEW.read_text())
    if len(prior["graphs"]) != len(new["graphs"]) or len(new["graphs"]) != 1800:
        raise ValueError("Diagnostic graph inventory changed")
    graph_differences = [(a,b) for a,b in zip(prior["graphs"],new["graphs"]) if a != b]
    if len(graph_differences) != 1:
        raise ValueError("Only the departure base graph may differ")
    a,b = graph_differences[0]
    if a["path"] != b["path"] or a["path"] != "capture/native/graphs/base/00000101.adapter.json":
        raise ValueError("Changed graph identity is not departure base")
    x = a["attributes"]["observed_evidence"]["participants"][0].pop("light_attributes")
    y = b["attributes"]["observed_evidence"]["participants"][0].pop("light_attributes")
    if (x,y) != ({"light_LeftBlinker":False,"light_RightBlinker":False},
                  {"light_LeftBlinker":True,"light_RightBlinker":False}) or a != b:
        raise ValueError("Departure graph changed nonlamp evidence")
    report = {"format":"worker-c144550-zero-late-controlled-comparison",
              "frame_count":900,"departure_frame":101,"changed_original_fields":"ego left lamp only",
              "changed_sources":changed,"diagnostic_sha256":{"late":sha(OLD),"zero":sha(NEW)},
              "physical_acceptance_claimed":False,"legal_acceptance_claimed":False}
    (HERE / "zero-exact-comparison-proof.json").write_text(json.dumps(report,indent=2)+"\n")
    return report


if __name__ == "__main__":
    report = compare()
    print(json.dumps({"frame_count":report["frame_count"],
                      "departure_frame":report["departure_frame"]},sort_keys=True))
