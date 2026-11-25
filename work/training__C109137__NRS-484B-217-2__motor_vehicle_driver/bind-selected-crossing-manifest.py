"""Bind the two selected crossing diagnostics and their source-proven fallbacks."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def proof(prefix, candidate, construction):
    offline = HERE / f"{prefix}-offline.log"
    compatibility = HERE / f"{prefix}-compatibility.json"
    negative = HERE / f"{prefix}-negative.log"
    analysis = HERE / f"{prefix}-analysis.log"
    saved = HERE / f"{prefix}-processing.json"
    public = read(compatibility)
    processed = read(saved)
    if (public.get("passed") is not True or public.get("candidate_id") != candidate or
            public.get("construction_sha256") != sha(HERE / construction) or
            processed.get("passed") is not True or processed.get("candidate_id") != candidate or
            processed.get("timestamp_joins", {}).get("frames") != 600):
        raise ValueError("Selected candidate proof differs: " + prefix)
    return {"offline": {"command": "runtime.py offline diagnostic candidate=" + candidate,
                        "exit_code": 0, "construction_sha256": sha(HERE / construction),
                        "log": offline.name, "log_sha256": sha(offline)},
            "compatibility": {"receipt": compatibility.name, "sha256": sha(compatibility),
                              "log": analysis.name, "negative_log": negative.name},
            "saved_processing": {"receipt": saved.name, "sha256": sha(saved)}}


def main():
    entries = []
    for probe in (1, 2):
        primary_prefix = f"selected-probe{probe}"
        primary = read(HERE / f"{primary_prefix}-manifest.json")["cases"][0]
        construction = f"{primary_prefix}-construction.json"
        entry = dict(primary)
        entry.update(proof(primary_prefix, "primary", construction))
        entry["candidate_risk"] = {"status": "physical",
                                   "reason": "Signal lead and stripe visibility may fail source review"}
        candidates = []
        for candidate in ("fallback1", "fallback2"):
            prefix = f"{primary_prefix}-{candidate}"
            diagnostic = read(HERE / f"{prefix}-manifest.json")["cases"][0]
            item = dict(diagnostic["candidates"][0])
            item.update(proof(prefix, candidate, item["construction"]))
            candidates.append(item)
        entry["candidates"] = candidates
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}
        entries.append(entry)
    manifest = {"format": "worker-execution-manifest", "assignment_id": HERE.name,
                "runtime_manifest_sha256": read(HERE / "selected-probe1-manifest.json")["runtime_manifest_sha256"],
                "status": "selected_crossing_diagnostic_only", "delivery_ready": False,
                "original_native_observed": False, "cases": entries}
    output = HERE / "selected-controlled-crossing-manifest.json"
    output.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"cases": len(entries), "candidates": sum(len(e["candidates"])
                      for e in entries), "manifest_sha256": sha(output)}))


if __name__ == "__main__":
    main()
