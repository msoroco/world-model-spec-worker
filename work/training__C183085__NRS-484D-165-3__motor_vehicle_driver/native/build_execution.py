"""Bind the exact selected CPU receipts and source-gated Native handoff."""

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent.parent
NATIVE = ROOT / "native"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((ROOT / "selected-proof-manifest.json").read_text())
    fallback_manifest = json.loads((ROOT / "selected-fallback-compat-manifest.json").read_text())
    fallback_entries = {entry["case_id"]: entry for entry in fallback_manifest["cases"]}
    manifest["status"] = "cpu_proved_original_native_pending"
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.split("__")[-1]
        fallback = fallback_entries[case]["candidates"][0]
        candidate = dict(fallback)
        version = "v2" if suffix.startswith("witness_") else "v1"
        source_dir = REPO / (".runtime-work/c183085-fallback-compat-" + version + "-" + suffix)
        for source, ending in (("compatibility.json", "compatibility.json"),
                               ("compatibility-analysis.log", "compatibility-analysis.log"),
                               ("negative-analysis.log", "negative-analysis.log")):
            shutil.copyfile(source_dir / source,
                            NATIVE / ("selected-" + suffix + "-fallback1-" + ending))
        receipt = NATIVE / ("selected-" + suffix + "-fallback1-compatibility.json")
        analysis = NATIVE / ("selected-" + suffix + "-fallback1-compatibility-analysis.log")
        negative = NATIVE / ("selected-" + suffix + "-fallback1-negative-analysis.log")
        assert sha(analysis) == json.loads(receipt.read_text())["log_sha256"]
        candidate["compatibility"] = {
            "receipt": str(receipt.relative_to(ROOT)),
            "log": str(analysis.relative_to(ROOT)),
            "negative_log": str(negative.relative_to(ROOT)),
            "sha256": sha(receipt),
        }
        offline_log = NATIVE / ("selected-" + suffix + "-fallback1-offline.log")
        candidate["offline"] = {
            "command": "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest work/" +
                       ROOT.name + "/selected-fallback-compat-manifest.json --case " + case +
                       " --candidate fallback1 --output .runtime-work/c183085-fallback-offline-v1-" + suffix,
            "construction_sha256": candidate["construction_sha256"],
            "exit_code": 0, "log": str(offline_log.relative_to(ROOT)),
            "log_sha256": sha(offline_log),
        }
        entry["candidate_risk"] = fallback_entries[case]["candidate_risk"]
        entry["candidates"] = [candidate]
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}
        entry["post_capture"]["command"] = (
            "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved "
            "--manifest work/" + ROOT.name + "/execution-manifest.json --case " + case +
            " --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER")
        entry["post_capture"]["test_command"] = (
            "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved "
            "--manifest work/" + ROOT.name + "/selected-shoulder-draft-manifest.json --case " + case +
            " --attempt .runtime-work/c183085-compat-" +
            ("v7" if suffix.startswith(("numeric_2_", "numeric_3_")) else "v6") + "-" + suffix +
            " --output .runtime-work/c183085-saved-" +
            ("v7" if suffix.startswith(("numeric_2_", "numeric_3_")) else "v6") + "-" + suffix +
            " --library runtime/library --validator .runtime-work/c385967-owner-decoder/.lake/build/bin/adapterCheck")
    path = ROOT / "execution-manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"cases": len(manifest["cases"]), "fallbacks": len(manifest["cases"]),
                      "sha256": sha(path)}))


if __name__ == "__main__":
    main()
