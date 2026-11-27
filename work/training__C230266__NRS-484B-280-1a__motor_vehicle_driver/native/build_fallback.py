"""Build a shared higher-throttle physical fallback without changing comparison response."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    alternatives = []
    for condition in ("a", "b"):
        primary = json.loads((HERE / ("selected-" + condition + "-construction.json")).read_text())
        alternate = json.loads(json.dumps(primary))
        runner = next(item for item in alternate["files"] if item["path"] == "runner.py")
        old = 'return {"throttle": 0.22, "brake": 0.0, "phase": "approach_request"}'
        new = 'return {"throttle": 0.32, "brake": 0.0, "phase": "approach_request"}'
        if runner["content"].count(old) != 1:
            raise ValueError("Primary approach throttle source changed")
        runner["content"] = runner["content"].replace(old, new)
        test = next(item for item in alternate["files"] if item["path"] == "tests/test_offline.py")
        anchor = '        self.assertEqual(control(25, 8, self.config["controller"])["brake"], 0)\n'
        if test["content"].count(anchor) != 1:
            raise ValueError("Primary offline test source changed")
        test["content"] = test["content"].replace(anchor, anchor +
            '        self.assertEqual(control(25, 8, self.config["controller"])["throttle"], 0.32)\n')
        alternate["status"] = "selected_fallback_cpu_construction_unverified"
        path = HERE / ("selected-" + condition + "-fallback1-construction.json")
        path.write_text(json.dumps(alternate, indent=2) + "\n")
        alternatives.append({"case_id": primary["case_id"],
                             "construction": "native/" + path.name,
                             "construction_sha256": sha(path)})
    manifest = json.loads((ROOT / "selected-compat-manifest.json").read_text())
    for entry, alternate in zip(manifest["cases"], alternatives):
        if entry["case_id"] != alternate["case_id"]:
            raise ValueError("Fallback case order differs")
        entry["candidates"] = [{"id": "fallback1", "construction": alternate["construction"],
                                 "construction_sha256": alternate["construction_sha256"],
                                 "trigger": {"source": "original pedestrian-due-care-trace.jsonl",
                                             "metric": "ego forward displacement over 30 seconds",
                                             "failure_condition": "measured displacement below 10 m despite surveyed pedestrian path"},
                                 "changed_knobs": ["approach throttle request 0.22 to 0.32"]}]
        entry["candidate_risk"] = {"status": "physical",
                                   "reason": "Original vehicle may fail to progress into the pedestrian encounter at the primary approach throttle; use source-measured displacement trigger."}
    path = ROOT / "selected-compat-manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"manifest_sha256": sha(path), "fallbacks": alternatives}))


if __name__ == "__main__":
    main()
