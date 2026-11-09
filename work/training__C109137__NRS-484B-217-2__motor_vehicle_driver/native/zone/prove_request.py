"""Eight exact positives and material copied-source negatives."""
import json
from pathlib import Path
import tempfile

from build import CASES, HERE, POLICIES, build
from check import check


def prove():
    build()
    positives, negatives = [], []
    for suffix in CASES:
        for candidate in POLICIES:
            source = HERE / "drafts" / suffix / candidate
            positives.append(check(source))
            for name, filename, old, new in (
                ("law", "assignment-source.json", "A driver may drive across", "A driver shall drive across"),
                ("cell", "assignment-source.json", '"control": "pavement_striping"', '"control": "traffic_control_device"'),
                ("stripe", "zone-adjoining.xodr", 'type="solid solid"', 'type="broken"'),
                ("adjoining", "zone-adjoining.xodr", 'connectingRoad="221"', 'connectingRoad="999"'),
                ("signal", "requested-tracks.jsonl", '"requested_left_indicator": true', '"requested_left_indicator": false'),
                ("track", "requested-tracks.jsonl", '"requested_speed_mps":', '"requested_speed_changed":'),
                ("case_plan", "case-plan.json", '"status": "alternative_pending"', '"status": "runnable"'),
            ):
                with tempfile.TemporaryDirectory() as tmp:
                    bundle = Path(tmp)
                    for item in ("assignment-source.json", "case-plan.json",
                                 "zone-adjoining.xodr", "requested-tracks.jsonl", "config.json"):
                        (bundle / item).write_bytes((source / item).read_bytes())
                    path = bundle / filename
                    before = path.read_text()
                    if old not in before:
                        if name == "signal" and suffix == "probe_2":
                            old, new = '"requested_left_indicator": false', '"requested_left_indicator": true'
                        else:
                            raise AssertionError(f"{name} mutation unavailable")
                    path.write_text(before.replace(old, new, 1))
                    try:
                        check(bundle)
                    except (ValueError, KeyError) as exc:
                        negatives.append({"case": suffix, "candidate": candidate,
                                          "mutation": name, "rejected": str(exc)})
                    else:
                        raise AssertionError(f"{suffix}/{candidate}/{name} accepted")
            with tempfile.TemporaryDirectory() as tmp:
                bundle = Path(tmp)
                for item in ("assignment-source.json", "case-plan.json",
                             "zone-adjoining.xodr", "requested-tracks.jsonl", "config.json"):
                    (bundle / item).write_bytes((source / item).read_bytes())
                assignment = json.loads((bundle / "assignment-source.json").read_text())
                plan = json.loads((bundle / "case-plan.json").read_text())
                cfg = json.loads((bundle / "config.json").read_text())
                changed = assignment["law_record"]["text"].replace(
                    "A driver may drive across", "A driver shall drive across", 1)
                assignment["law_record"]["text"] = changed
                plan["source_law"]["text"] = changed
                cfg["source_text"] = changed
                import hashlib
                for name, value in (("assignment-source.json", assignment),
                                    ("case-plan.json", plan)):
                    (bundle / name).write_text(json.dumps(value, indent=2) + "\n")
                cfg["assignment_sha256"] = hashlib.sha256(
                    (bundle / "assignment-source.json").read_bytes()).hexdigest()
                cfg["case_plan_sha256"] = hashlib.sha256(
                    (bundle / "case-plan.json").read_bytes()).hexdigest()
                (bundle / "config.json").write_text(json.dumps(cfg, indent=2) + "\n")
                try:
                    check(bundle)
                except (ValueError, KeyError) as exc:
                    negatives.append({"case": suffix, "candidate": candidate,
                                      "mutation": "consistently_rehashed_law",
                                      "rejected": str(exc)})
                else:
                    raise AssertionError(f"{suffix}/{candidate}/rehash accepted")
    result = {
        "format": "c109137-zone-request-proof-v1",
        "positives": positives, "negatives": negatives,
        "positive_count": len(positives), "negative_count": len(negatives),
        "original_native_observed": False, "delivery_ready": False}
    (HERE / "request-proof.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    result = prove()
    print(json.dumps({"positive_count": result["positive_count"],
                      "negative_count": result["negative_count"]}))
