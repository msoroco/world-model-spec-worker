"""Build source-shaped synthetic school-bus diagnostics for saved-only checks."""

import hashlib
import json
from pathlib import Path

from package_spec import AID

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.selected-draft.json"
EXAMPLE = ROOT / "runtime/fixtures/example.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, value, compact=False):
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False,
                               **({"separators": (",", ":")} if compact else {"indent": 2})) + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("diagnostic exceeds 2 MiB")


def build():
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest = json.loads(MANIFEST.read_text())
    base = json.loads(EXAMPLE.read_text())
    mapping = [json.loads(line) for line in base["files"]["video_frames.jsonl"].splitlines()]
    trace = [json.loads(line) for line in base["files"]["trace.jsonl"].splitlines()]
    for entry, case in zip(manifest["cases"], plan["cases"]):
        suffix = case["case_id"].removeprefix(AID + "__")
        fixture = json.loads(json.dumps(base))
        active = case["requested_active_transport_phase"]
        rows = []
        for i, mapped in enumerate(mapping):
            rows.append({"frame": i, "native_frame": mapped["carla_frame"],
                         "time_s": mapped["time_s"], "actor_ids": ["synthetic-bus"],
                         "bus_speed_mps": trace[i]["speed_mps"],
                         "bus_position_xyz_m": trace[i]["position_m"],
                         "bus_heading_deg": trace[i]["heading_deg"],
                         "transporting_pupils_to_or_from_school": active})
        history = {"source_kind": "synthetic_diagnostic_fixture", "assignment_id": AID,
                   "case_id": case["case_id"], "reviewed_site_sha256": "a" * 64,
                   "map_sha256": "b" * 64,
                   "school_bus_classification": {"qualifying_definition_branch": "synthetic-only",
                       "source": "synthetic-only", "all_exclusions_reviewed": True,
                       "reviewed_facts": ["synthetic"], "exclusion_dispositions": ["synthetic"]},
                   "driver_actor_id": "synthetic-driver", "bus_actor_id": "synthetic-bus",
                   "transport_direction": "to_school", "transport_source": "synthetic-trip",
                   "pupil_count": 12 if active else 0,
                   "pupil_presence_source": "synthetic-pupil-source",
                   "sidewalk_source": "synthetic-sidewalk", "samples": rows}
        history_text = json.dumps(history, sort_keys=True) + "\n"
        measurement = {"maximum_active_transport_speed_mph": max((row["bus_speed_mps"] * 2.2369362920544 for row in rows if active), default=None),
                       "active_transport_frame_count": len(rows) if active else 0,
                       "above_55_mph_observed": False,
                       "maximum_all_speed_mph": max(row["bus_speed_mps"] * 2.2369362920544 for row in rows),
                       "review_limit": "synthetic diagnostic only"}
        measurement_text = json.dumps(measurement, sort_keys=True) + "\n"
        trace_text = base["files"]["trace.jsonl"]
        frame_rows = [{**mapped, "video_frame": i, "native_frame": mapped["carla_frame"]}
                      for i, mapped in enumerate(mapping)]
        frame_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in frame_rows)
        receipt = {"source_kind": "synthetic_diagnostic_fixture", "diagnostic_fixture": True,
                   "case_id": case["case_id"],
                   "history_sha256": hashlib.sha256(history_text.encode()).hexdigest(),
                   "trace_sha256": hashlib.sha256(trace_text.encode()).hexdigest(),
                   "frame_map_sha256": hashlib.sha256(frame_text.encode()).hexdigest(),
                   "measurement_sha256": hashlib.sha256(measurement_text.encode()).hexdigest(),
                   "physical_acceptance": False, "legal_verdict": None}
        fixture["files"].update({"school-bus-history.json": history_text,
                                 "school-bus-measurement.json": measurement_text,
                                 "trace.jsonl": trace_text, "video_frames.jsonl": frame_text,
                                 "original-source-receipt.json": json.dumps(receipt, sort_keys=True) + "\n"})
        generator = HERE / "diagnostics" / (suffix + "-generator.json")
        put(generator, fixture, compact=True)
        recipe = HERE / "diagnostics" / (suffix + "-recipe.json")
        put(recipe, {"format": "worker-fixture-recipe", "sources": [{
            "path": "diagnostic-input.json", "source": "runtime/fixtures/example.json",
            "sha256": sha(EXAMPLE)}], "generator": {
                "source": str(generator.relative_to(ROOT)), "sha256": sha(generator)}})
        keys = ("school_bus_classification", "bus_speed", "pupil_transport_phase")
        requirements = [{"disposition_index": d["disposition_index"],
                         "requirement": d["requirement"], "source": d["source"],
                         "output_key": keys[d["disposition_index"]],
                         "method": "source_sealed_school_bus_measurement", "value_type": "object",
                         "kind": "measured", "inputs": ["school-bus-history.json",
                                                      "original-source-receipt.json", "trace.jsonl"]}
                        for d in plan["requirement_dispositions"]]
        contract = HERE / "diagnostics" / (suffix + "-measurement-contract.json")
        put(contract, {"format": "worker-measurement-contract", "case_id": case["case_id"],
                       "requirements": requirements,
                       "negative": {"remove": ["school-bus-history.json"],
                                    "error_contains": "Missing required source: school-bus-history.json"}})
        entry["fixture_recipe"] = str(recipe.relative_to(ROOT))
        entry["measurement_contract"] = str(contract.relative_to(HERE))
        entry["measurement_procedure"] = {"entrypoint": "analysis.py",
                                         "method": "source-sealed Native bus speed and pupil trip readback"}
    put(MANIFEST, manifest)
    return len(manifest["cases"])


if __name__ == "__main__":
    print("school-bus compatibility inputs:", build())
