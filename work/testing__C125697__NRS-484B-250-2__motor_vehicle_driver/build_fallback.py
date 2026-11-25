"""Construct a bounded lower-speed median approach fallback per exact case."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build():
    manifest_path = ROOT / "execution-manifest.compat-draft.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[1]
        primary = json.loads((ROOT / entry["construction"]).read_text())
        fallback = json.loads(json.dumps(primary))
        implementation = next(item for item in fallback["files"]
                              if item["path"] == "native_capture.py")
        code = implementation["content"]
        replacements = (("min(.55, .25 * (8.0 - speed))",
                         "min(.35, .20 * (5.0 - speed))"),
                        ("error / .5", "error / .7"),
                        ("min(.8, .2 * (speed - 8.0))",
                         "min(.8, .2 * (speed - 5.0))"))
        for before, after in replacements:
            if code.count(before) != 1:
                raise ValueError("primary route controller changed: " + before)
            code = code.replace(before, after)
        implementation["content"] = code
        path = ROOT / ("fallback-" + suffix + "-construction.json")
        path.write_text(json.dumps(fallback, indent=2) + "\n")
        entry["candidate_risk"] = {
            "status": "physical",
            "reason": "Primary bounded control may overshoot the median approach or fail to complete a settled crossing within 45 seconds."}
        entry["candidates"] = [{
            "id": "fallback1", "construction": path.name,
            "construction_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "changed_knobs": ["requested approach target 8 to 5 m/s",
                              "throttle cap 0.55 to 0.35",
                              "steering error divisor 0.5 to 0.7"],
            "trigger": {
                "source": "original native_trace.json body/speed history and scene.json crossing bounds",
                "metric": "ego speed and body exit across 900 original frames",
                "failure_condition": "ego exceeds 8 m/s within 5 m of the median crossing or does not exit it within 900 frames"}}]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    build()
