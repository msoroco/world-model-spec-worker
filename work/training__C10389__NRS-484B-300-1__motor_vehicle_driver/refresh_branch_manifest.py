"""Refresh construction hashes in the unselected branch diagnostic manifest."""
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    path=HERE/'branch-draft-manifest.json';manifest=json.loads(path.read_text())
    for entry in manifest['cases']:
        entry['construction_sha256']=sha(HERE/entry['construction'])
        for fallback in entry['candidates']:
            fallback['construction_sha256']=sha(HERE/fallback['construction'])
    path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    return sha(path)

if __name__=='__main__':print(main())
