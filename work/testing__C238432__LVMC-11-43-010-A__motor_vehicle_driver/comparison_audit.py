"""Independently compare source-bound clockwise and counterclockwise captures."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from analysis import measure
from direction import ASSIGNMENT

COMPARISON="roundabout_circulation_direction"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(counterclockwise,clockwise,plan):
    first=Path(counterclockwise)
    second=Path(clockwise)
    planned=next((row for row in json.loads(Path(plan).read_text())["comparisons"]
                  if row["comparison_id"]==COMPARISON),None)
    ids=[ASSIGNMENT+"__counterclockwise",ASSIGNMENT+"__clockwise"]
    if planned is None or planned["case_ids"]!=ids:
        raise ValueError("exact roundabout comparison plan differs")
    a=measure(first)[0]
    b=measure(second)[0]
    if [a["case_id"],b["case_id"]]!=ids:
        raise ValueError("comparison original case identities differ")
    if sha(first/"map.json")!=sha(second/"map.json"):
        raise ValueError("comparison original map differs")
    fixture=(first/"fixture-provenance.json").is_file()
    if fixture!=(second/"fixture-provenance.json").is_file():
        raise ValueError("comparison source profiles differ")
    expected=9 if fixture else 900
    if (a["map_name"]!=b["map_name"] or
            a["source_frames"]!=expected or b["source_frames"]!=expected or
            a["observed_direction"]!="counterclockwise" or
            b["observed_direction"]!="clockwise"):
        raise ValueError("original compared direction or duration differs")
    compared={"case_ids":ids,"observed_directions":[a["observed_direction"],
              b["observed_direction"]],"legal_judgment":"unresolved"}
    return {"format":"c238432-independent-direction-comparison-v1",
        "comparison_id":COMPARISON,"case_ids":ids,
        "fixed_conditions":planned["fixed_conditions"],
        "deliberate_differences":planned["deliberate_differences"],
        "measured":compared,"source_hashes":{
            "counterclockwise_map":sha(first/"map.json"),
            "counterclockwise_history":sha(first/"history.json"),
            "clockwise_map":sha(second/"map.json"),
            "clockwise_history":sha(second/"history.json")},
        "diagnostic_fixture":fixture,"physical_acceptance":False,
        "legal_judgment":"unresolved"}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--counterclockwise",type=Path,required=True)
    parser.add_argument("--clockwise",type=Path,required=True)
    parser.add_argument("--comparison-id",default=ASSIGNMENT+"__"+COMPARISON)
    parser.add_argument("--plan",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.comparison_id!=ASSIGNMENT+"__"+COMPARISON or args.output.exists():
        raise ValueError("exact comparison output or identity differs")
    result=audit(args.counterclockwise,args.clockwise,args.plan)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
