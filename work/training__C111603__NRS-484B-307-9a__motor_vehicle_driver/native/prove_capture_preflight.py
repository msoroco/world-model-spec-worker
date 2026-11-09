"""CPU preflight of the original capture entrypoint; never starts CARLA."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from build import CASE, HERE, write


def prove():
    positive = negative = 0
    for suffix in ("witness_1", "witness_2"):
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            bundle = HERE / "drafts" / suffix / candidate
            command = [sys.executable, str(HERE / "capture.py"), "--check", "--bundle", str(bundle)]
            result = subprocess.run(command, text=True, capture_output=True)
            if result.returncode:
                raise RuntimeError(result.stderr)
            value = json.loads(result.stdout)
            assert value["case_id"] == CASE.name + "__" + suffix
            assert value["candidate_id"] == candidate
            assert value["frames"] == 480 and not value["delivery_ready"]
            positive += 1
            with tempfile.TemporaryDirectory(prefix="c111603-preflight-") as name:
                changed = Path(name) / "bundle"
                shutil.copytree(bundle, changed)
                config = changed / "config.json"
                edited = json.loads(config.read_text())
                edited["other_blueprint"] = "vehicle.unknown"
                write(config, edited)
                rejected = subprocess.run([sys.executable, str(HERE / "capture.py"),
                                           "--check", "--bundle", str(changed)],
                                          text=True, capture_output=True)
                if rejected.returncode == 0:
                    raise AssertionError("Changed capture blueprint passed preflight")
                negative += 1
    result = {"format": "c111603-3079a-capture-preflight-proof-v1",
              "assignment_id": CASE.name, "positive_count": positive,
              "negative_count": negative, "carla_imported": False,
              "simulation_started": False, "original_native_observed": False,
              "delivery_ready": False}
    write(HERE / "capture-preflight-proof.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(prove(), sort_keys=True))
