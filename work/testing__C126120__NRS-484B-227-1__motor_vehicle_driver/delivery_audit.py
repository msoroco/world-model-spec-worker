"""Independent, saved-only provenance and physical target audit."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from analysis import SOURCES, build_report


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt):
    root = Path(attempt)
    report = build_report(root)
    result = json.loads((root/"result.json").read_text())
    seal = json.loads((root/"capture-seal.json").read_text())
    provenance = json.loads((root/"acquisition-provenance.json").read_text())
    if (seal.get("format") != "worker-sealed-capture" or
            seal.get("provenance_kind") != "native" or
            seal.get("diagnostic_fixture") or
            seal.get("restoration",{}).get("restored") is not True or
            provenance.get("provenance_kind") != "native" or
            provenance.get("diagnostic_fixture")):
        raise ValueError("Native sealed capture and restoration proof required")
    if any(k in result for k in ("legal_verdict","compliant","violating")):
        raise ValueError("delivery result contains legal verdict")
    originals = (*SOURCES,"overview.mkv","approach.mkv","reference_corner.mkv",
                 "driver_reference.mkv")
    for name in originals:
        path = root/name
        if not path.is_file() or not path.stat().st_size:
            raise ValueError("missing original delivery source: "+name)
        digest = seal.get("sources",{}).get(name)
        if digest is None:
            raise ValueError("capture seal omits original source: "+name)
        # The pinned sealer's tree records a SHA digest for every original source.
        if isinstance(digest,str) and digest != sha(path):
            raise ValueError("sealed original source changed: "+name)
    observed = report["measurements"]["median_uturn_measurement"]["value"]
    if result.get("measured_values") != observed:
        raise ValueError("result measurements differ from original saved geometry")
    targets = {item.get("target"):item for item in result.get("target_checks",[])}
    for label, value in (("realized multiple-movement U-turn",observed["multiple_movement_observed"]),
                         ("full-body opening crossing without closed-divider contact",
                          observed["engineering_crossing_observed"])):
        if label not in targets or targets[label].get("measured") is not value:
            raise ValueError("physical target lacks matching saved evidence: "+label)
    if not all(result.get(key) is True for key in
               ("setup_confirmed","behavior_attempted","maneuver_completed")):
        raise ValueError("physical setup, attempt or maneuver not confirmed")
    if not all(item.get("matched") is True for item in targets.values()):
        raise ValueError("declared original physical target not matched")
    if not observed["engineering_crossing_observed"] or not observed["u_turn_orientation_observed"]:
        raise ValueError("original opening crossing or U-turn orientation absent")
    return {"delivery_physical_audit_passed":True,"legal_verdict_claimed":False,
            "source_hashes":{name:sha(root/name) for name in originals}}
