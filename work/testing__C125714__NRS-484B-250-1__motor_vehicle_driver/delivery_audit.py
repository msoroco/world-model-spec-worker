"""Independent source and comparison audit for saved C125714 attempts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from analysis import build_report
from crossing_audit import audit_comparison


CAMERAS = ("overview.mkv", "approach.mkv", "reference_corner.mkv",
           "driver_reference.mkv")
ORIGINALS = ("trace.jsonl", "video_frames.jsonl", "road.xodr", "carla_recorder.log",
             "reviewed-context.json", "intersection-context.json",
             "ego-body-history.jsonl", "other-body-history.jsonl",
             "controller-history.jsonl", *CAMERAS)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read(path):
    return json.loads(Path(path).read_text())


def audit_reviewed_context(path):
    """Recheck the retained site packet against original map and scene context."""
    path = Path(path)
    packet = _read(path / "reviewed-context.json")
    context = _read(path / "intersection-context.json")
    provenance = _read(path / "acquisition-provenance.json")
    if (provenance.get("reviewed_context_sha256") != sha(path / "reviewed-context.json") or
            context.get("reviewed_context_sha256") != sha(path / "reviewed-context.json")):
        raise ValueError("reviewed context provenance differs from retained packet")
    if (context.get("crossing") != packet.get("crossing") or
            context.get("law_context") != packet.get("law_context")):
        raise ValueError("reviewed crossing or law context differs from original scene")
    law = packet["law_context"]
    if law.get("map_source") != sha(path / "road.xodr"):
        raise ValueError("reviewed map differs from original OpenDRIVE")
    if (law.get("public_access") is not True or law.get("human_driver") is not True or
            law.get("devices") != [] or
            not all(law.get(key) for key in ("public_access_source",
                                             "device_inventory_source",
                                             "driver_scope_source"))):
        raise ValueError("reviewed public-highway, driver or device context incomplete")
    if (law.get("approach_relation") == "crossing" and
            law.get("ego_highway") == law.get("other_highway")):
        raise ValueError("reviewed crossing lacks distinct highway identities")
    return {"reviewed_context_sha256": sha(path / "reviewed-context.json"),
            "original_map_sha256": sha(path / "road.xodr")}


def audit_attempt(path):
    """Verify original closure and source binding before using measurements."""
    path = Path(path)
    seal = _read(path / "capture-seal.json")
    exit_receipt = _read(path / "native-exit.json")
    provenance = _read(path / "acquisition-provenance.json")
    if provenance.get("provenance_kind") != "native" or provenance.get("diagnostic_fixture") is not False:
        raise ValueError("original Native acquisition required")
    if (seal.get("format") != "worker-sealed-capture" or
            seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"] or
            seal.get("restoration", {}).get("restored") is not True):
        raise ValueError("Native closure sequence or restoration unverified")
    if any(seal.get("encoder_exit_codes", {}).get(name.removesuffix(".mkv")) != 0
           for name in CAMERAS):
        raise ValueError("four camera encoder exits unverified")
    if (exit_receipt.get("event") != "native_exit" or
            exit_receipt.get("capture_seal_sha256") != sha(path / "capture-seal.json") or
            exit_receipt.get("native_process_exit_code") != 0 or
            exit_receipt.get("capture_command_failed") is not False):
        raise ValueError("Native exit does not bind a successful sealed capture")
    acquisition = _read(path / "acquisition.json")
    for name in ORIGINALS:
        source = path / name
        if (not source.is_file() or acquisition.get(name, {}).get("kind") != "original_native" or
                acquisition[name].get("sha256") != sha(source) or
                seal.get("sources", {}).get(name) != sha(source)):
            raise ValueError("original source missing or changed: " + name)
    site_review = audit_reviewed_context(path)
    report = build_report(path)
    measurement = report["measurements"]["crossing_entry_measurement"]["value"]
    if measurement["legal_judgment"] != "unresolved":
        raise ValueError("legal judgment must remain unresolved in physical audit")
    return {"source_hashes": {name: sha(path / name) for name in ORIGINALS},
            "site_review": site_review,
            "measurements": measurement, "legal_verdict_claimed": False,
            "physical_acceptance_claimed": False}


def audit_pair(left, right, declared_differences):
    """Require two independently sealed attempts and one realized variable."""
    left_audit, right_audit = audit_attempt(left), audit_attempt(right)
    def trace(path):
        path = Path(path)
        context = _read(path / "intersection-context.json")
        samples = {}
        for party in ("ego", "other"):
            samples[party + "_samples"] = [json.loads(line) for line in
                (path / (party + "-body-history.jsonl")).read_text().splitlines() if line.strip()]
        return {"context": context["law_context"], "crossing": context["crossing"],
                **samples}
    comparison = audit_comparison(trace(left), trace(right), declared_differences)
    return {"left": left_audit, "right": right_audit,
            "comparison": comparison, "legal_verdict_claimed": False}
