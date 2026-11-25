"""Bind four selected public positive and missing-bus-motion-source negative receipts."""
import hashlib
import json
import shutil
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parents[1]
MANIFEST = FOLDER / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        label = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1'):
            choice = entry if candidate == 'primary' else entry['candidates'][0]
            suffix = '-v5'
            source = REPO / '.runtime-work' / f'c230241-compat-{label}-{candidate}{suffix}'
            target = FOLDER / 'proofs' / label / candidate
            target.mkdir(parents=True, exist_ok=True)
            for original, dest in (('compatibility.json', 'compatibility.json'),
                                   ('compatibility-analysis.log', 'analysis.log'),
                                   ('negative-analysis.log', 'negative-analysis.log')):
                shutil.copyfile(source / original, target / dest)
            receipt = json.loads((target / 'compatibility.json').read_text())
            if (not receipt['passed'] or receipt['negative_removed'] != 'bus_motion.jsonl'
                    or sha(target / 'analysis.log') != receipt['log_sha256']):
                raise ValueError('Copied public compatibility proof differs')
            choice['compatibility'] = {'receipt': str((target / 'compatibility.json').relative_to(FOLDER)),
                                       'sha256': sha(target / 'compatibility.json'),
                                       'log': str((target / 'analysis.log').relative_to(FOLDER)),
                                       'negative_log': str((target / 'negative-analysis.log').relative_to(FOLDER))}
            choice['negative'] = {'log': str((target / 'negative-analysis.log').relative_to(FOLDER))}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'public_receipts': 4, 'manifest_sha256': sha(MANIFEST)}))


if __name__ == '__main__':
    main()
