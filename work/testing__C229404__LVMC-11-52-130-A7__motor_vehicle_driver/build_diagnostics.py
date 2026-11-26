"""Build source-shaped, explicitly synthetic compatibility inputs for exact cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = REPO / "runtime/fixtures/example.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("returned diagnostic exceeds 2 MiB")
    path.write_bytes(raw)
    return sha(raw)


def make(case: dict, base: dict) -> None:
    ident = case["case_id"]
    slug = ident.removeprefix(ROOT.name + "__")
    folder = ROOT / "diagnostics" / slug
    files = dict(base["files"])
    generic = [json.loads(line) for line in files["trace.jsonl"].splitlines() if line]
    mapping = [json.loads(line) for line in files["video_frames.jsonl"].splitlines() if line]
    if len(generic) != 9 or len(mapping) != 9:
        raise ValueError("unexpected pinned generic diagnostic frame count")
    mouth_x = {"front": 100.0, "within_5ft": 103.0,
               "outside_5ft": 105.0}[case["position_target"]]
    context = {
        "case_id": ident, "driveway_kind": case["driveway_kind"],
        "map_sha256": sha(files["road.xodr"].encode()),
        "mouth_start_xy": [mouth_x, 0.0], "mouth_end_xy": [mouth_x, 3.0],
        "observed_conditions": {key: case[key] for key in
            ("driveway_kind", "activity", "position_target", "driver_relationship",
             "necessity_or_postal_context")},
    }
    for name in ("mouth", "frontage", "driveway_use", "responsible_person",
                 "relationship", "purpose", "traffic_direction", "postal_status"):
        context[name + "_source"] = {
            "kind": "synthetic_diagnostic_only", "name": name,
            "case_id": ident, "physical_evidence": False,
        }
    vertices = [[x, y, z] for x in (98.0, 102.0)
                for y in (1.0, 2.0) for z in (0.0, 1.5)]
    body = [{"frame": index, "carla_frame": video["carla_frame"],
             "time_s": index / 20, "vehicle_vertices": vertices,
             "speed_mps": 0.0, "control_state": case["activity"]}
            for index, video in enumerate(mapping)]
    body_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in body)
    context_text = json.dumps(context, sort_keys=True) + "\n"
    files["original-attempt/reviewed-context.json"] = context_text
    files["original-attempt/body-control-trace.jsonl"] = body_text
    files["original-attempt/capture-receipt.json"] = json.dumps({
        "assignment_id": ROOT.name, "case_id": ident,
        "source_kind": "synthetic_fixture", "diagnostic_fixture": True,
        "context_sha256": sha(context_text.encode()),
        "trace_sha256": sha(body_text.encode()),
        "map_sha256": sha(files["road.xodr"].encode()),
        "frame_count": len(body), "fps": 20,
        "physical_acceptance_claimed": False,
    }, sort_keys=True) + "\n"
    files["fixture-provenance.json"] = json.dumps({
        "diagnostic_fixture": True, "physical_acceptance_claimed": False,
        "source": "pinned example telemetry plus exact synthetic driveway branch",
        "case_id": ident,
    }, sort_keys=True) + "\n"
    capture_manifest = json.loads(files["capture/manifest.json"])
    capture_manifest["case_id"] = ident
    capture_manifest["source_run"] = "synthetic_exact_driveway_diagnostic"
    files["capture/manifest.json"] = json.dumps(capture_manifest, indent=2) + "\n"
    specification = dict(base, files=files)
    spec_path = folder / "diagnostic.json"
    digest = write(spec_path, specification)
    relative = str(spec_path.relative_to(REPO))
    write(folder / "fixture-recipe.json", {
        "format": "worker-fixture-recipe",
        "sources": [{"path": "diagnostic-input.json", "source": relative,
                     "sha256": digest}],
        "generator": {"source": relative, "sha256": digest},
    })
    requirement = json.loads((ROOT / "case-plan.json").read_text())["requirement_dispositions"][0]
    write(folder / "measurement-contract.json", {
        "format": "worker-measurement-contract", "case_id": ident,
        "requirements": [{
            "disposition_index": 0, "requirement": requirement["requirement"],
            "source": requirement["source"],
            "output_key": "driveway_position_measurement",
            "method": "measure_driveway_position", "kind": "measured",
            "value_type": "object",
            "inputs": ["original-attempt/reviewed-context.json",
                       "original-attempt/body-control-trace.jsonl",
                       "original-attempt/capture-receipt.json", "road.xodr"],
        }],
        "negative": {"remove": ["original-attempt/reviewed-context.json"],
                     "error_contains": "Missing required source: original-attempt/reviewed-context.json"},
    })


def main() -> None:
    base = json.loads(BASE.read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    for case in plan["cases"]:
        make(case, base)
    print("built", len(plan["cases"]), "explicit synthetic driveway recipes and contracts")


if __name__ == "__main__":
    main()
