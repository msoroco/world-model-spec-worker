"""Bind exact public positive and missing-source negative traffic proofs."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind():
    manifest_path = FOLDER / 'traffic-execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    target = FOLDER / 'compatibility'
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        for variant, selected in [('primary', entry)] + [
                (candidate['id'], candidate) for candidate in entry['candidates']]:
            scratch = REPO / '.runtime-work' / f'c229977-traffic-public-{suffix.split("_")[-1]}-{variant}-v5'
            receipt = json.loads((scratch / 'compatibility.json').read_text())
            if (not receipt['passed'] or
                    receipt['construction_sha256'] != selected['construction_sha256'] or
                    receipt['case_id'] != entry['case_id'] or
                    receipt['candidate_id'] != variant):
                raise ValueError('Public traffic receipt differs from selected construction')
            name = suffix + '-' + variant
            receipt_path = target / (name + '.json')
            receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
            for original, output in (
                    ('compatibility-analysis.log', name + '-analysis.log'),
                    ('negative-analysis.log', name + '-negative.log')):
                content = (scratch / original).read_text()
                log = target / output
                log.write_text(content.rstrip() + '\n')
            selected['compatibility'] = {
                'receipt': str(receipt_path.relative_to(FOLDER)),
                'sha256': sha(receipt_path),
                'log': str((target / (name + '-analysis.log')).relative_to(FOLDER)),
                'negative_log': str((target / (name + '-negative.log')).relative_to(FOLDER))}
            if variant == 'primary':
                entry['negative'] = {'log': selected['compatibility']['negative_log']}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return sha(manifest_path)


if __name__ == '__main__':
    print(bind())
