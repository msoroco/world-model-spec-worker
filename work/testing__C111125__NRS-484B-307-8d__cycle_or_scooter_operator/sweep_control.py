"""Apply a reviewed judgment-sweep control without treating a request as evidence.

The local Native adapter supplies the method named by the reviewed control
packet. Its returned receipt records the request; original 20 Hz readbacks are
measured separately by sweep_measurement.py after capture.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from prepare_reviewed_sweeps import ASSIGNMENT, linked


def apply_sweep_control(proposal: dict, case_id: str, authority_root: Path,
                        control_ref: dict, adapter: object) -> dict:
    if not proposal.get("sweeps_expanded") or not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("expanded exact sweep proposal required")
    cases = [row for row in proposal.get("cases", []) if row.get("case_id") == case_id]
    if len(cases) != 1 or cases[0].get("target_type") != "judgment_sweep":
        raise ValueError("exact generated sweep case missing")
    case = cases[0]
    specs = [row for row in proposal.get("sweep_specs", [])
             if row.get("sweep_id") == case.get("sweep_id")]
    if len(specs) != 1 or specs[0].get("status") != "complete":
        raise ValueError("complete reviewed sweep specification missing")
    spec = specs[0]
    if (case_id not in spec.get("selection_order", []) or
            case.get("sweep_spec_version") != spec.get("spec_version") or
            len(spec.get("axes", [])) != 1):
        raise ValueError("generated case differs from reviewed sweep specification")
    axis = spec["axes"][0]
    variable = axis["variable"]
    value = case.get("sweep_point", {}).get(variable)
    if (not isinstance(value, (int, float)) or isinstance(value, bool) or
            not math.isfinite(value) or value < axis["min"] or value > axis["max"]):
        raise ValueError("generated setpoint outside reviewed physical range")
    binding = spec.get("numeric_control_binding", {})
    root = Path(authority_root).resolve()
    path = linked(root, control_ref)
    control_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if (binding.get("control_sha256") != control_sha or
            proposal.get("reviewed_sweep_authority", {}).get("control_sha256") != control_sha):
        raise ValueError("reviewed numeric control source differs")
    control = json.loads(path.read_text(encoding="utf-8"))
    if (control.get("reviewed_original_controls") is not True or
            control.get("site_sha256") != proposal.get("reviewed_sweep_authority", {}).get("site_sha256")):
        raise ValueError("reviewed original numeric control missing")
    source_controls = [row for row in control.get("supported_numeric_controls", [])
                       if row.get("name") == variable]
    if len(source_controls) != 1:
        raise ValueError("numeric control absent from original source")
    source = source_controls[0]
    method_name = binding.get("adapter_method")
    readback = binding.get("original_readback_field")
    if (not isinstance(method_name, str) or not method_name.isidentifier() or
            source.get("adapter_method") != method_name or
            source.get("original_readback_field") != readback or
            source.get("unit") != axis.get("unit")):
        raise ValueError("numeric adapter and readback differ from reviewed source")
    method = getattr(adapter, method_name, None)
    if not callable(method):
        raise ValueError("reviewed Native numeric adapter method missing")
    receipt = method(value=value, case_id=case_id, control_sha256=control_sha)
    if (not isinstance(receipt, dict) or receipt.get("case_id") != case_id or
            receipt.get("control_sha256") != control_sha or
            receipt.get("requested_setpoint") != value or
            receipt.get("original_readback_field") != readback):
        raise ValueError("Native numeric control request receipt missing or changed")
    return {"case_id": case_id, "variable": variable, "requested_setpoint": value,
            "unit": axis["unit"], "control_sha256": control_sha,
            "original_readback_field": readback, "adapter_receipt": receipt,
            "physical_acceptance": False, "legal_verdict": None}
