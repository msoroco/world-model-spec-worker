"""Return the contrast primary compatibility receipt and diagnostic logs."""
import hashlib
import json
import shutil
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
SOURCE = ROOT / '.runtime-work/c229597-selected-contrast-compat-v1'
DEST = P / 'selected-proofs/contrast/primary'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    for name, out in [('compatibility.json', 'compatibility.json'),
                      ('compatibility-analysis.log', 'analysis.log'),
                      ('negative-analysis.log', 'negative.log')]:
        shutil.copyfile(SOURCE / name, DEST / out)
    manifest_path = P / 'selected-pair-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = manifest['cases'][1]
    entry['compatibility'] = {
        'receipt': 'selected-proofs/contrast/primary/compatibility.json',
        'sha256': sha(DEST / 'compatibility.json'),
        'log': 'selected-proofs/contrast/primary/analysis.log',
        'negative_log': 'selected-proofs/contrast/primary/negative.log'}
    entry['negative'] = {'log': entry['compatibility']['negative_log']}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'receipt_sha256': entry['compatibility']['sha256'],
                      'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
