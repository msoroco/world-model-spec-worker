"""CPU-check each exact analyzer selected by prospective Native preflight."""

import json
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
if not output or not Path(output).resolve().is_relative_to(ROOT / ".runtime-work"):
    raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
from native_delivery_preflight import selected_measurements, sha  # noqa: E402
from prove_delivery_acceptance import source_for  # noqa: E402


entries = json.loads((HERE / "execution-manifest.json").read_text())["cases"]
for entry in entries:
    case_id = entry["case_id"]
    attempt = source_for(case_id.split("__")[-1])
    analyzer = entry["measurement_procedure"]["entrypoint"]
    result = selected_measurements(attempt, entry, case_id, {analyzer: sha(attempt / analyzer)})
    if result["source_frame_count"] != 900 or result["observed_signal_pattern_matches_plan"] is not True:
        raise ValueError("Selected exact analyzer failed original diagnostic source")
    try:
        selected_measurements(attempt, entry, case_id, {})
    except ValueError as error:
        if "Selected analyzer is not sealed original implementation" not in str(error):
            raise
    else:
        raise AssertionError("Unsealed analyzer was accepted")
    print("PASS", case_id)
print("All", len(entries), "exact analyzers measured 900 original diagnostic frames and rejected unsealed code")
