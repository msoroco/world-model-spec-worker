"""Retain the seven pinned compatibility proofs and bind their source hashes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-number", type=int, required=True)
    args = parser.parse_args()
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        source = ROOT / ".runtime-work" / f"c179789-compat-{suffix}-{args.run_number}"
        if not source.is_dir():
            raise ValueError("missing compatibility output: " + suffix)
        receipt = json.loads((source / "compatibility.json").read_text(encoding="utf-8"))
        if (receipt.get("passed") is not True or receipt.get("case_id") != case_id or
                receipt.get("construction_sha256") != entry["construction_sha256"] or
                receipt.get("fixture_recipe_sha256") != sha(ROOT / entry["fixture_recipe"])):
            raise ValueError("incomplete or stale compatibility receipt: " + suffix)
        names = {
            "receipt": (source / "compatibility.json", HERE / f"cpu-compat-{suffix}-receipt.json"),
            "log": (source / "compatibility-analysis.log", HERE / f"cpu-compat-{suffix}-analysis.log"),
            "negative": (source / "negative-analysis.log", HERE / f"cpu-compat-{suffix}-negative.log"),
            "command": (ROOT / ".runtime-work" / f"c179789-compat-{suffix}-{args.run_number}.log",
                        HERE / f"cpu-compat-{suffix}.log"),
        }
        for src, dst in names.values():
            if not src.is_file():
                raise ValueError("missing compatibility proof file: " + str(src))
            shutil.copyfile(src, dst)
            if dst.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("compatibility proof exceeds return limit")
        if (receipt["log_sha256"] != sha(names["log"][1]) or
                receipt["negative_log_sha256"] != sha(names["negative"][1])):
            raise ValueError("compatibility source log changed: " + suffix)
        entry["compatibility"] = {"receipt": names["receipt"][1].name,
                                  "sha256": sha(names["receipt"][1]),
                                  "log": names["log"][1].name}
        entry["negative"] = {"log": names["negative"][1].name}
        result["tests"] = [test for test in result["tests"]
                           if test.get("log") != names["command"][1].name]
        result["tests"].append({
            "command": ".venv-cpu/bin/python runtime.py compatibility --manifest work/"
                       + HERE.name + "/execution-manifest.json --case " + case_id
                       + " --output .runtime-work/c179789-compat-" + suffix + "-"
                       + str(args.run_number) + " --library runtime/library --validator "
                       + ".runtime-work/c179789-decoder/.lake/build/bin/adapterCheck",
            "exit_code": 0, "log": names["command"][1].name,
            "sha256": sha(names["command"][1]),
        })
        print(json.dumps({"case_id": case_id,
                          "receipt_sha256": entry["compatibility"]["sha256"]}))
    manifest["status"] = "partial_offline_and_compatibility_cpu_proved"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    result["readiness_kind"] = "seven_exact_offline_and_compatibility_cpu_proved_physical_preparation_pending"
    result["reason"] = ("Seven exact construction bundles pass pinned offline checks, and all seven "
                        "source-bound diagnostic cases pass the full pinned compatibility pipeline "
                        "including negative source rejection. Reviewed numeric/site inputs, a runtime "
                        "capture runner interface, physical preparation, canonical acquisition mappings, "
                        "and remaining batch packages are worker-owned CPU preparation. Synthetic "
                        "diagnostics do not establish physical motion, visibility or legal acceptance.")
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
