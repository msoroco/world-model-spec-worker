"""Rebind the sealed-history signal-distance diagnostic after audit changes."""
import hashlib
import json
import shlex
import subprocess
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parent.parent
receipt_path = folder / 'signal-advance-receipt.json'
receipt = json.loads(receipt_path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for item in receipt['probes']:
    log = folder / item['log']
    with log.open('w') as output:
        subprocess.run(shlex.split(item['command']), cwd=repo, stdout=output,
                       stderr=subprocess.STDOUT, check=True)
    item['result'] = json.loads(log.read_text())
    item['log_sha256'] = sha(log)
receipt['auditor_sha256'] = sha(folder / 'signal_advance_audit.py')
receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({item['branch']: item['result']['observed_continuous_approach_distance_m']
                  for item in receipt['probes']}))
