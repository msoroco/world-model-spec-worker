"""Build exact synthetic barrier diagnostics for saved-only contract testing."""

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
    base_trace = [json.loads(line) for line in base["files"]["trace.jsonl"].splitlines()]
    for entry, case in zip(manifest["cases"], plan["cases"]):
        suffix = case["case_id"].removeprefix(AID + "__")
        fixture = json.loads(json.dumps(base))
        rows = []
        for i, mapped in enumerate(mapping):
            lateral = 3.0 if suffix == "wide_clearance" else 1.4
            rows.append({"frame": mapped["carla_frame"], "time_s": mapped["time_s"],
                         "speed_mps": base_trace[i]["speed_mps"], "ego_footprint_vertices":
                         [[float(i), lateral - .4], [float(i + 1), lateral - .4],
                          [float(i + 1), lateral + .4], [float(i), lateral + .4]],
                         "barrier_contact": False})
        packet = {"assignment_id": AID, "map_id": "synthetic-diagnostic-map",
                  "highway_id": "synthetic-diagnostic-highway",
                  "city_highway_status": "unresolved", "barrier_id": "diagnostic-barrier",
                  "barrier_rectangle": [3.0, 0.0, 5.0, 1.0],
                  "barrier_geometry_source": "synthetic diagnostic geometry",
                  "road_y_bounds": [-4.0, 6.0],
                  "surrounding_conditions_source": "synthetic diagnostic surroundings",
                  "original_trace_id": "synthetic-diagnostic-trace", "ego_actor_id": "ego",
                  "driver_actor_id": "diagnostic-driver", "reviewed_site_sha256": "a" * 64,
                  "route_candidate": case["route_candidate"],
                  "case_id": case["case_id"], "frames": rows}
        packet_text = json.dumps(packet, sort_keys=True) + "\n"
        trace_text = base["files"]["trace.jsonl"]
        frame_rows = [{**mapped, "video_frame": i, "native_frame": mapped["carla_frame"]}
                      for i, mapped in enumerate(mapping)]
        frame_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in frame_rows)
        receipt = {"source_kind": "synthetic_diagnostic_fixture", "diagnostic_fixture": True,
                   "case_id": case["case_id"], "packet_sha256": hashlib.sha256(packet_text.encode()).hexdigest(),
                   "trace_sha256": hashlib.sha256(trace_text.encode()).hexdigest(),
                   "frame_map_sha256": hashlib.sha256(frame_text.encode()).hexdigest(),
                   "physical_acceptance": False, "legal_verdict": None}
        fixture["files"].update({"barrier-packet.json": packet_text, "trace.jsonl": trace_text,
                                 "video_frames.jsonl": frame_text,
                                 "original-source-receipt.json": json.dumps(receipt, sort_keys=True) + "\n"})
        generator = HERE / "diagnostics" / (suffix + "-generator.json")
        put(generator, fixture, compact=True)
        recipe = HERE / "diagnostics" / (suffix + "-recipe.json")
        put(recipe, {"format": "worker-fixture-recipe", "sources": [{
            "path": "diagnostic-input.json", "source": "runtime/fixtures/example.json",
            "sha256": sha(EXAMPLE)}], "generator": {
                "source": str(generator.relative_to(ROOT)), "sha256": sha(generator)}})
        output_keys = ("ego_body_motion", "highway_city_context", "barrier_body_clearance")
        requirements = [{"disposition_index": d["disposition_index"],
                         "requirement": d["requirement"], "source": d["source"],
                         "output_key": output_keys[d["disposition_index"]],
                         "method": "source_sealed_barrier_measurement", "value_type": "object",
                         "kind": "measured", "inputs": ["barrier-packet.json",
                                                     "original-source-receipt.json", "trace.jsonl"]}
                        for d in plan["requirement_dispositions"]]
        contract = HERE / "diagnostics" / (suffix + "-measurement-contract.json")
        put(contract, {"format": "worker-measurement-contract", "case_id": case["case_id"],
                       "requirements": requirements,
                       "negative": {"remove": ["barrier-packet.json"],
                                    "error_contains": "Missing required source: barrier-packet.json"}})
        entry["fixture_recipe"] = str(recipe.relative_to(ROOT))
        entry["measurement_contract"] = str(contract.relative_to(HERE))
        entry["measurement_procedure"] = {"entrypoint": "analysis.py",
                                          "method": "source-sealed original barrier body and route readback"}
    put(MANIFEST, manifest)
    return len(manifest["cases"])


if __name__ == "__main__":
    print("barrier compatibility inputs:", build())
