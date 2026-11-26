"""Build seven case-specific synthetic signal diagnostics and source contracts."""

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


def write(path, value, *, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {"separators": (",", ":")} if compact else {"indent": 2}
    path.write_text(json.dumps(value, ensure_ascii=False, **kwargs) + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("diagnostic input exceeds 2 MiB")


def build():
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest = json.loads(MANIFEST.read_text())
    base = json.loads(EXAMPLE.read_text())
    base_frames = [json.loads(line) for line in base["files"]["video_frames.jsonl"].splitlines()]
    if len(base_frames) != 9:
        raise ValueError("pinned nine-frame diagnostic example changed")
    geometry_ref = {"path": "synthetic-diagnostic-geometry", "sha256": "a" * 64}
    signal_ref = {"path": "synthetic-diagnostic-official-head", "sha256": "b" * 64}
    for entry, case in zip(manifest["cases"], plan["cases"]):
        if entry["case_id"] != case["case_id"]:
            raise ValueError("exact selected case order changed")
        suffix = case["case_id"].removeprefix(AID + "__")
        fixture = json.loads(json.dumps(base))
        entry_frame = (7 if suffix == "enters_red" else
                       99 if suffix in ("stops_red", "yellow_non_alone") else 4)
        frames = []
        for index, mapped in enumerate(base_frames):
            state = "green" if index < 2 else "yellow" if index < 6 else "red"
            selected = {"signal_id": "head1", "route_id": "ego_route", "kind": "vehicular",
                        "official": True, "facing_ego": True, "state": state,
                        "flashing": False,
                        "companion_lamps_on": ["head-companion"]
                        if suffix == "yellow_non_alone" and state == "yellow" else [],
                        "source": signal_ref}
            signals = [selected]
            if suffix == "red_other_route":
                signals.append({"signal_id": "head-other", "route_id": "cross_route",
                                "kind": "vehicular", "official": True,
                                "facing_ego": False, "state": "red", "source": signal_ref})
            distance = index - entry_frame + .25
            frames.append({"frame": index, "source_frame": index,
                           "time_s": index / 20, "native_frame": mapped["carla_frame"],
                           "native_time_s": mapped["time_s"],
                           "position_m": [float(index), 0.0],
                           "heading_deg": 0.0, "speed_mps": 5.0,
                           "ego_front_signed_distance_m": distance,
                           "ego_geometry_source": geometry_ref,
                           "signals": signals})
        trace_text = base["files"]["trace.jsonl"]
        packet = {"layout": "one_way_to_two_way_intersection",
                  "route_id": "ego_route", "signal_id": "head1",
                  "intersection_polygon": geometry_ref,
                  "route_connectivity": geometry_ref,
                  "device_route_binding": signal_ref,
                  "native_result": {"path": "trace.jsonl",
                                    "sha256": hashlib.sha256(trace_text.encode()).hexdigest()},
                  "frames": frames}
        packet_text = json.dumps(packet, sort_keys=True) + "\n"
        receipt = {"source_kind": "synthetic_diagnostic_fixture",
                   "diagnostic_fixture": True, "case": suffix, "fps": 20,
                   "frame_count": 9,
                   "signal_packet_sha256": hashlib.sha256(packet_text.encode()).hexdigest(),
                   "trace_sha256": hashlib.sha256(trace_text.encode()).hexdigest(),
                   "physical_acceptance": False, "legal_verdict": None}
        fixture["files"].update({"original-signal-packet.json": packet_text,
                                 "original-source-receipt.json": json.dumps(receipt, sort_keys=True) + "\n"})
        generator = HERE / "diagnostics" / (suffix + "-generator.json")
        write(generator, fixture, compact=True)
        recipe = {"format": "worker-fixture-recipe", "sources": [{
            "path": "diagnostic-input.json", "source": "runtime/fixtures/example.json",
            "sha256": sha(EXAMPLE)}],
            "generator": {"source": str(generator.relative_to(ROOT)),
                          "sha256": sha(generator)}}
        recipe_path = HERE / "diagnostics" / (suffix + "-recipe.json")
        write(recipe_path, recipe)
        requirements = []
        output_keys = ("selected_facing_signal_sequence", "signal_vs_entry",
                       "comparison_isolation", "intersection_entry_bracket",
                       "entry_governance")
        for index, disposition in enumerate(plan["requirement_dispositions"]):
            if case["case_id"] not in disposition["case_ids"]:
                continue
            requirements.append({"disposition_index": disposition["disposition_index"],
                "requirement": disposition["requirement"], "source": disposition["source"],
                "output_key": output_keys[index], "method": "source_sealed_signal_measurement",
                "value_type": "object", "kind": "measured",
                "inputs": ["original-signal-packet.json", "original-source-receipt.json",
                           "trace.jsonl"]})
        contract = {"format": "worker-measurement-contract",
                    "case_id": case["case_id"], "requirements": requirements,
                    "negative": {"remove": ["original-signal-packet.json"],
                                 "error_contains": "Missing required source: original-signal-packet.json"}}
        contract_path = HERE / "diagnostics" / (suffix + "-measurement-contract.json")
        write(contract_path, contract)
        entry["fixture_recipe"] = str(recipe_path.relative_to(ROOT))
        entry["measurement_contract"] = str(contract_path.relative_to(HERE))
        entry["measurement_procedure"] = {"entrypoint": "analysis.py",
                                         "method": "original bound signal and body-entry bracket"}
    write(MANIFEST, manifest)
    return len(manifest["cases"])


if __name__ == "__main__":
    print("exact signal diagnostics:", build())
