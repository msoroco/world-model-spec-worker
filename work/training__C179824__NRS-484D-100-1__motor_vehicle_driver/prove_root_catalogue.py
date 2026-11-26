"""Record root exact-case CPU catalogue tests without throwaway work files."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
COMMANDS = [
    [sys.executable, "-B", str(ROOT / "runner.py"), "--check"],
    [sys.executable, "-B", "-m", "unittest", "discover", "-s",
     str(ROOT / "tests"), "-p", "test_native.py", "-v"],
]
env = dict(os.environ)
env["PYTHONPATH"] = str(ROOT)
receipts = []
for index, argv in enumerate(COMMANDS, 1):
    result = subprocess.run(argv, cwd=REPO, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    log = ROOT / f"root-catalogue-{index}.log"
    log.write_text("\n".join(line.rstrip() for line in result.stdout.rstrip().splitlines()) + "\n")
    if result.returncode:
        raise ValueError(f"Root catalogue test {index} failed: {result.stdout}")
    receipts.append({"command": " ".join(argv), "exit_code": 0,
                     "log": log.name, "sha256": hashlib.sha256(log.read_bytes()).hexdigest()})
result_path = ROOT / "result.json"
package = json.loads(result_path.read_text())
package["tests"] = receipts
result_path.write_text(json.dumps(package, indent=2) + "\n")
print(json.dumps({"tests": len(receipts), "all_passed": True}))
