"""Rebind the two measured-risk witness alternatives to the current 30 s profile."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    manifest = json.loads((HERE / "current-v2-probe-manifest.json").read_text())
    manifest["format"] = "worker-unselected-current-v2-witness-fallback-manifest"
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        original = json.loads((HERE / "draft-execution-manifest.json").read_text())
        draft = next(x for x in original["cases"] if x["case_id"] == entry["case_id"])
        primary = json.loads((HERE / entry["construction"]).read_text())
        primary_config = json.loads(next(x["content"] for x in primary["files"] if x["path"] == "config.json"))
        entry["candidates"] = []
        for name in ("fallback1", "fallback2"):
            candidate = next(x for x in draft["candidates"] if x["id"] == name)
            older = json.loads((HERE / candidate["construction"]).read_text())
            older_config = json.loads(next(x["content"] for x in older["files"] if x["path"] == "config.json"))
            changed = candidate["changed_knobs"]
            assert len(changed) == 1
            updated = json.loads(json.dumps(primary))
            for item in updated["files"]:
                if item["path"] == "config.json":
                    config = json.loads(json.dumps(primary_config))
                    config["candidate_id"] = name
                    for knob in changed:
                        config["engineering_knobs"][knob] = older_config["engineering_knobs"][knob]
                    item["content"] = json.dumps(config, indent=2) + "\n"
            updated["status"] = "unselected_current_runtime_risk_alternative"
            output = HERE / "draft-current-fallbacks" / suffix / name / "construction.json"
            write(output, updated)
            entry["candidates"].append({**candidate,
                "construction": str(output.relative_to(HERE)),
                "construction_sha256": sha(output)})
    target = HERE / "current-v2-witness-fallback-manifest.json"
    write(target, manifest)
    print(json.dumps({"manifest_sha256": sha(target),
                      "case_count": len(manifest["cases"]),
                      "fallback_count": sum(len(x["candidates"]) for x in manifest["cases"])}))


if __name__ == "__main__":
    main()
