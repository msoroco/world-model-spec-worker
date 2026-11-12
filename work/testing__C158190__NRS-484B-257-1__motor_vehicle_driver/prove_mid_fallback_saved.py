"""Replay each 4 m/s physical fallback into recorded-only saved processing."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path

import prove_stable_saved as stable

HERE = Path(__file__).resolve().parent
stable.MANIFEST = HERE / 'mid-speed-compatibility-manifest.json'


def main():
    manifest_sha = hashlib.sha256(stable.MANIFEST.read_bytes()).hexdigest()
    entry = json.loads(stable.MANIFEST.read_text())['cases'][0]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(stable.run_one, entry, candidate['id'], manifest_sha): candidate['id']
                   for candidate in entry['candidates']}
        for future in as_completed(futures):
            print(json.dumps(future.result()), flush=True)
    if hashlib.sha256(stable.MANIFEST.read_bytes()).hexdigest() != manifest_sha:
        raise ValueError('Manifest changed during fallback saved proofs')


if __name__ == '__main__':
    main()
