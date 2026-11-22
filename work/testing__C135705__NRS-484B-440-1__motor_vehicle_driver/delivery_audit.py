"""Independent saved-source audit for each C135705 Native attempt.

It rejects missing, stale or inconsistent original evidence and checks the
requested physical contrast. It does not assert legal or optical acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from native_construction import ASSIGNMENT
from saved_measurement import SOURCES,VIDEOS,body_rect,rows


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt, *, diagnostic_test=False):
    root=Path(attempt).resolve()
    report_path=root/"standing-measurement.json"
    if not report_path.is_file():raise ValueError("missing saved-only standing measurement")
    report=json.loads(report_path.read_text())
    scene=json.loads((root/"scene.json").read_text())
    case=scene.get("case_id")
    if not case.startswith(ASSIGNMENT+"__") or report.get("case_id")!=case:
        raise ValueError("exact case binding differs")
    seal=root/"capture-seal.json"
    if report.get("capture_seal_sha256")!=sha(seal):raise ValueError("stale capture seal")
    sealed=json.loads(seal.read_text())
    expected_kind="synthetic_fixture" if diagnostic_test else "native"
    if (sealed.get("format")!="worker-sealed-capture" or
        sealed.get("provenance_kind")!=expected_kind or
        sealed.get("diagnostic_fixture") is not diagnostic_test or
        sealed.get("restoration",{}).get("restored") is not True):
        raise ValueError("capture seal provenance or restoration differs")
    provenance=json.loads((root/"acquisition-provenance.json").read_text())
    if provenance.get("provenance_kind")!=expected_kind or provenance.get("diagnostic_fixture") is not diagnostic_test:
        raise ValueError("acquisition provenance differs")
    if report.get("provenance_kind")!=expected_kind or report.get("physical_acceptance_claimed") is not False:
        raise ValueError("measurement provenance or physical claim differs")
    source_hashes=report.get("source_sha256",{})
    for name in (*SOURCES,*VIDEOS,"acquisition.json"):
        if source_hashes.get(name)!=sha(root/name):
            raise ValueError("missing or stale original source: "+name)
        if name in sealed.get("sources",{}) and sealed["sources"][name]!=source_hashes[name]:
            raise ValueError("sealed original source changed: "+name)
    measured=report.get("measured",{})
    result=json.loads((root/"result.json").read_text())
    if result.get("measured_values")!=measured or result.get("case_id")!=case:
        raise ValueError("saved result differs from original measurement")
    mapping=rows(root/"video_frames.jsonl")
    standing=rows(root/"standing-body-history.jsonl")
    passing=rows(root/"passing-body-history.jsonl")
    props=rows(root/"occluder-body-history.jsonl")
    mechanical=rows(root/"mechanical-attempt-history.jsonl")
    count=measured.get("frame_count")
    if count!=sealed.get("frames") or any(len(x)!=count for x in (mapping,standing,passing,props,mechanical)):
        raise ValueError("original frame count differs")
    for index,group in enumerate(zip(mapping,standing,passing,props,mechanical)):
        frame=group[0].get("carla_frame");time=group[0].get("time_s")
        if group[0].get("video_frame")!=index or any(r.get("frame")!=frame or
            not math.isclose(r.get("time_s",math.inf),time,abs_tol=1e-4) for r in group[1:]):
            raise ValueError("original frame/time identity failed")
        if mechanical[index].get("standing_actor_id")!=standing[index].get("actor_id"):
            raise ValueError("mechanical failure actor identity failed")
        body_rect(standing[index]);body_rect(passing[index])
        if len(props[index].get("actors",[]))!=len(scene.get("sight_occluders_xy_m",[])):
            raise ValueError("physical occluder actors missing")
        for prop in props[index]["actors"]:body_rect(prop)
    media=report.get("media_full_decode",{})
    for name in VIDEOS:
        receipt=media.get(name,{})
        if receipt.get("sha256")!=source_hashes[name] or receipt.get("frames_fully_decoded")!=count or receipt.get("fps")!=20:
            raise ValueError("missing full media decode receipt: "+name)
    if measured.get("statutory_sight_distance_m")!=60.96 or measured.get("legal_verdict_claimed") is not False:
        raise ValueError("numeric sight boundary or verdict claim invalid")
    if not measured.get("standing_stationary_engineering_check") or not measured.get("mechanical_disable_and_brake_attempt_observed"):
        raise ValueError("standing actor or failure mechanism not observed")
    sight=measured.get("sight_probes",{})
    pair=[sight.get(f"{side}:60.960m",{}).get("clear_xy_geometry") for side in ("negative_x","positive_x")]
    suffix=case.removeprefix(ASSIGNMENT+"__")
    if suffix=="passage_clear_view":
        expected=measured.get("physical_passage_observed") is True and pair==[True,True]
    elif suffix=="passage_blocked":
        expected=(measured.get("physical_passage_observed") is False and
                  measured.get("opposite_route_corridor_interference") is True and pair==[True,True])
    elif suffix=="view_occluded_both":
        expected=measured.get("physical_passage_observed") is True and pair==[False,False] and len(measured.get("actual_prop_bodies_xy_m",[]))==2
    else:raise ValueError("unknown exact case")
    if not expected:raise ValueError("requested physical contrast not measured")
    if not all(item.get("matched") is True for item in result.get("target_checks",[])):
        raise ValueError("saved physical target check not matched")
    return {"format":"worker-delivery-audit","case_id":case,"status":"cpu_source_audit_passed",
            "measurement_sha256":sha(report_path),"capture_seal_sha256":sha(seal),
            "frame_count":count,"original_source_hashes":source_hashes,
            "physical_acceptance_claimed":False,"diagnostic_audit_test_passed":diagnostic_test,
            "optical_visibility":"requires live image review",
            "legal_verdict_claimed":False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument("attempt")
    args=parser.parse_args();print(json.dumps(audit(args.attempt),indent=2))


if __name__=="__main__":main()
