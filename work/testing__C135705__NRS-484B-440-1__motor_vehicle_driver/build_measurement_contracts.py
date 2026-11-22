"""Bind every exact case to original streams and selected source disposition."""
from __future__ import annotations

import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def write(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+"\n")


def main():
    plan=json.loads((HERE/"case-plan.json").read_text())
    if len(plan["requirement_dispositions"])!=1:
        raise ValueError("selected disposition count differs")
    disposition=plan["requirement_dispositions"][0]
    source=disposition["source"]
    for entry in plan["cases"]:
        case_id=entry["case_id"]
        suffix=case_id.removeprefix(HERE.name+"__")
        scene=json.loads((HERE/"cases"/suffix/"scene.json").read_text())
        contract={"format":"worker-measurement-contract","case_id":case_id,
            "requirements":[{"disposition_index":0,"requirement":disposition["requirement"],
                "source":source,"kind":"measured","method":"measure_original",
                "output_key":"standing_passage_two_sided_sight_measurement","value_type":"object",
                "inputs":["standing-body-history.jsonl","passing-body-history.jsonl",
                    "occluder-body-history.jsonl","mechanical-attempt-history.jsonl",
                    "video_frames.jsonl","trace.jsonl", "approach.mkv","reference_corner.mkv"]}],
            "numeric_boundary":{"feet":200,"metres":60.96,"directions":["negative_x","positive_x"],
                                "probes_m":scene["sight_probe_distances_m"]},
            "negative":{"remove":["standing-body-history.jsonl"],
                        "error_contains":"Missing required source: standing-body-history.jsonl"},
            "independent_auditor":"delivery_audit.py",
            "unresolved_judgments":["highway and district classification","off-pavement practicability",
                "adequacy of unobstructed width","optical clear view in original pixels",
                "disabled while on traveled way, impossible to avoid stopping, temporary duration"]}
        write(HERE/"cases"/suffix/"measurement-contract.json",contract)
        if suffix=="passage_clear_view":write(HERE/"measurement-contract.json",contract)
    print("three source-bound measurement contracts")


if __name__=="__main__":main()
