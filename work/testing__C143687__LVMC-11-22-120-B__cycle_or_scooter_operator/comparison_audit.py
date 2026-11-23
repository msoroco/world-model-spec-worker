"""Independent fixed-condition comparison checks on source-bound measurements."""
from __future__ import annotations


def audit_pair(plan: dict, left: dict, right: dict, comparison_id: str) -> dict:
    comparison = next((item for item in plan["comparisons"] if item["comparison_id"] == comparison_id), None)
    if comparison is None:
        raise ValueError("undeclared comparison")
    if [left.get("case_id"), right.get("case_id")] != comparison["case_ids"]:
        raise ValueError("case identities do not match comparison")
    for name, record in (("left", left), ("right", right)):
        if record.get("source_kind") != "original_native_measurement" or record.get("frames") != 900 or record.get("sign_posted_original_frames") != 900:
            raise ValueError(f"{name} original Native measurement incomplete")
        if not record.get("packet_sha256") or not record.get("site_sha256") or not record.get("designation_source"):
            raise ValueError(f"{name} original source binding missing")
    if left["site_sha256"] != right["site_sha256"] or left["designation_source"] != right["designation_source"]:
        raise ValueError("fixed designation, sign or geometry changed")
    if comparison_id == "posted_roadway_entry":
        if not left["roadway_frames"] or right["roadway_frames"]:
            raise ValueError("roadway entry contrast not observed")
    elif comparison_id == "trail_vs_roadway_use":
        if not left["roadway_frames"] or right["roadway_frames"] or not right["trail_frames"]:
            raise ValueError("trail versus roadway contrast not observed")
    else:
        raise ValueError("unsupported comparison")
    return {"comparison_id": comparison_id, "case_ids": comparison["case_ids"], "fixed_site_sha256": left["site_sha256"], "source_packet_sha256": [left["packet_sha256"], right["packet_sha256"]], "legal_assessment": "unresolved"}
