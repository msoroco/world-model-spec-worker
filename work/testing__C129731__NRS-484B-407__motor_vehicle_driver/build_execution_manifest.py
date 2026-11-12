"""Bind the six exact constructions to current CPU receipts without setting ready."""
import hashlib
import json
from pathlib import Path
import shlex

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = (
    ("curve-short", "diagnostic-execution-manifest.json", "curve-short-offline-v6.log", "compatibility.json", "negative-analysis.log", "processing.json", "curve-short"),
    ("at", "diagnostic-at-manifest.json", "rebound-at-offline.log", "rebound-at-compatibility.json", "rebound-at-negative-analysis.log", "rebound-at-processing.json", "at"),
    ("beyond", "diagnostic-beyond-manifest.json", "rebound-beyond-offline.log", "rebound-beyond-compatibility.json", "rebound-beyond-negative-analysis.log", "rebound-beyond-processing.json", "beyond"),
    ("crest-short", "diagnostic-crest-short-manifest.json", "rebound-crest-short-offline.log", "rebound-crest-short-compatibility.json", "rebound-crest-short-negative-analysis.log", "rebound-crest-short-processing.json", "crest-short"),
    ("crest-at", "diagnostic-crest-at-manifest.json", "rebound-crest-at-offline.log", "rebound-crest-at-compatibility.json", "rebound-crest-at-negative-analysis.log", "rebound-crest-at-processing.json", "crest-at"),
    ("crest-beyond", "diagnostic-crest-beyond-manifest.json", "rebound-crest-beyond-offline.log", "rebound-crest-beyond-compatibility.json", "rebound-crest-beyond-negative-analysis.log", "rebound-crest-beyond-processing.json", "crest-beyond"),
)
PROMOTED = (
    "canonical-at-approach-b", "canonical-at-near-b", "canonical-at-approach-a", "canonical-at-near-a",
    "canonical-short-approach-b", "canonical-short-near-b", "canonical-short-approach-a",
    "canonical-short-near-a", "canonical-beyond-approach-b", "canonical-beyond-near-b",
    "canonical-beyond-approach-a", "canonical-beyond-near-a",
)


def read(name):
    return json.loads((HERE / name).read_text())


def sha(name):
    return hashlib.sha256((HERE / name).read_bytes()).hexdigest()


def claim(tests, name):
    matches = [t for t in tests if t["log"] == name and t["exit_code"] == 0 and t["sha256"] == sha(name)]
    if len(matches) != 1:
        raise ValueError("Current exact CPU claim missing: " + name)
    return matches[0]


def compatibility(name, negative):
    receipt = read(name)
    if receipt.get("passed") is not True or receipt.get("negative_log_sha256") != sha(negative):
        raise ValueError("Compatibility/negative proof changed: " + name)
    if receipt.get("log_sha256") != sha("analysis.log"):
        raise ValueError("Compatibility analysis log changed: " + name)
    return {"receipt": name, "sha256": sha(name), "log": "analysis.log", "negative_log": negative}


def saved_proof(tests, name):
    record = read(name)
    if record.get("passed") is not True or record.get("recorded_only") is not True or record.get("originals_preserved") is not True:
        raise ValueError("Recorded-only proof missing: " + name)
    test = claim(tests, name)
    tokens = shlex.split(test["command"])
    if "--output" not in tokens:
        raise ValueError("Saved proof output path absent: " + name)
    saved_dir = tokens[tokens.index("--output") + 1]
    return {"recorded_only": True, "command": test["command"],
            "feedback_command": "cat " + shlex.quote(saved_dir + "/v0001/feedback.json"),
            "test_log": name, "test_log_sha256": sha(name), "test_exit_code": 0}


def build():
    result = read("result.json")
    tests = result["tests"]
    entries = []
    for slug, manifest_name, offline_name, compat_name, negative_name, saved_name, proof_slug in CASES:
        manifest = read(manifest_name)
        entry = dict(manifest["cases"][0])
        selected = entry["case_id"]
        offline = claim(tests, offline_name)
        entry["offline"] = {"command": offline["command"], "exit_code": 0,
                            "log": offline_name, "log_sha256": sha(offline_name),
                            "construction_sha256": entry["construction_sha256"]}
        entry["compatibility"] = compatibility(compat_name, negative_name)
        entry["negative"] = {"log": negative_name}
        entry["post_capture"] = saved_proof(tests, saved_name)
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON", "host_env_var": "CARLA_HOST",
                                   "port_env_var": "CARLA_PORT"}
        physical = "physical-proofs/" + proof_slug + "/receipt.json"
        entry["physical_preparation"] = {"receipt": physical, "sha256": sha(physical)}
        acceptance = "delivery-proofs/" + proof_slug + "/acceptance.json"
        if (HERE / acceptance).is_file():
            declared = read(acceptance)
            if (declared.get("case_id") != selected or declared.get("script_sha256") != sha("delivery_audit.py") or
                    declared.get("test_log_sha256") != sha(declared["test_log"]) or
                    declared.get("negative_log_sha256") != sha(declared["negative_log"])):
                raise ValueError("Stale diagnostic delivery audit proof: " + selected)
            entry["delivery_acceptance"] = declared
        fallback_manifest = read("diagnostic-" + slug + "-fallback-manifest.json")
        alternatives = []
        for candidate in fallback_manifest["cases"][0]["candidates"]:
            item = dict(candidate)
            prefix = slug + "-" + item["id"]
            offline_name = prefix + "-offline.log"
            receipt_name = prefix + "-compatibility.json"
            negative_name = prefix + "-negative-analysis.log"
            saved_name = prefix + "-processing.json"
            offline = claim(tests, offline_name)
            item["offline"] = {"command": offline["command"], "exit_code": 0,
                               "log": offline_name, "log_sha256": sha(offline_name),
                               "construction_sha256": item["construction_sha256"]}
            item["compatibility"] = compatibility(receipt_name, negative_name)
            item["post_capture"] = saved_proof(tests, saved_name)
            alternatives.append(item)
        if {x["id"] for x in alternatives} != {"fallback1", "fallback2", "fallback3"}:
            raise ValueError("Three distinct fallback proofs required: " + selected)
        entry["candidates"] = alternatives
        entries.append(entry)
    for name in PROMOTED:
        source_manifest = read("diagnostic-" + name + "-manifest.json")
        entry = dict(source_manifest["cases"][0])
        selected = entry["case_id"]
        offline_name = name + "-branch-offline.log"
        offline = claim(tests, offline_name)
        entry["offline"] = {"command": offline["command"], "exit_code": 0,
                            "log": offline_name, "log_sha256": sha(offline_name),
                            "construction_sha256": entry["construction_sha256"]}
        entry["compatibility"] = compatibility(name + "-branch-compatibility.json",
                                                name + "-branch-negative-analysis.log")
        entry["negative"] = {"log": name + "-branch-negative-analysis.log"}
        entry["post_capture"] = saved_proof(tests, name + "-branch-processing.json")
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON", "host_env_var": "CARLA_HOST",
                                   "port_env_var": "CARLA_PORT"}
        physical = "physical-proofs/" + name + "/receipt.json"
        receipt = read(physical)
        if receipt["case_id"] != selected or receipt["construction_sha256"] != entry["construction_sha256"]:
            raise ValueError("Stale distinct-case physical proof: " + selected)
        entry["physical_preparation"] = {"receipt": physical, "sha256": sha(physical)}
        acceptance = "delivery-proofs/" + name + "/acceptance.json"
        if (HERE / acceptance).is_file():
            declared = read(acceptance)
            if (declared.get("case_id") != selected or declared.get("script_sha256") != sha("delivery_audit.py") or
                    declared.get("test_log_sha256") != sha(declared["test_log"]) or
                    declared.get("negative_log_sha256") != sha(declared["negative_log"])):
                raise ValueError("Stale distinct-case delivery audit proof: " + selected)
            entry["delivery_acceptance"] = declared
        fallback_manifest = read("diagnostic-" + name + "-fallback-manifest.json")
        alternatives = []
        for candidate in fallback_manifest["cases"][0]["candidates"]:
            item = dict(candidate)
            prefix = name + "-" + item["id"]
            candidate_offline = prefix + "-offline.log"
            proof = claim(tests, candidate_offline)
            item["offline"] = {"command": proof["command"], "exit_code": 0,
                               "log": candidate_offline, "log_sha256": sha(candidate_offline),
                               "construction_sha256": item["construction_sha256"]}
            item["compatibility"] = compatibility(prefix + "-compatibility.json",
                                                    prefix + "-negative-analysis.log")
            item["post_capture"] = saved_proof(tests, prefix + "-processing.json")
            alternatives.append(item)
        if {x["id"] for x in alternatives} != {"fallback1", "fallback2", "fallback3"}:
            raise ValueError("Three distinct fallback proofs required: " + selected)
        entry["candidates"] = alternatives
        entries.append(entry)
    base = read(CASES[0][1])
    output = {"format": "worker-execution-manifest", "assignment_id": HERE.name,
              "runtime_manifest_sha256": base["runtime_manifest_sha256"], "cases": entries}
    (HERE / "execution-manifest.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(entries), "fallbacks": sum(len(x["candidates"]) for x in entries),
                      "manifest_sha256": sha("execution-manifest.json")}))


if __name__ == "__main__":
    build()
