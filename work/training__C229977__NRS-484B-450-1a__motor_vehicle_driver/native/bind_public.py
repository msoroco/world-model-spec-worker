"""Bind completed public compatibility receipts to selected constructions."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parent.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    path = FOLDER / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for index, entry in enumerate(manifest['cases'], 1):
        for variant, selected in [('primary', entry)] + [
                (candidate['id'], candidate) for candidate in entry['candidates']]:
            version = 'v9'
            source = REPO / '.runtime-work' / (
                f'c229977-public-probe_{index}-{variant}-{version}')
            receipt = json.loads((source / 'compatibility.json').read_text())
            if not receipt['passed'] or receipt['construction_sha256'] != selected['construction_sha256']:
                raise ValueError('Public proof is not selected and passing')
            target = FOLDER / 'compatibility'
            target.mkdir(exist_ok=True)
            name = f'probe_{index}-{variant}'
            (target / (name + '.json')).write_text(
                json.dumps(receipt, indent=2) + '\n')
            for original, suffix in [('compatibility-analysis.log', 'analysis.log'),
                                     ('negative-analysis.log', 'negative.log')]:
                contents = (source / original).read_text()
                if any(line.rstrip() != line for line in contents.splitlines()):
                    raise ValueError('Public log has trailing whitespace')
                (target / (name + '-' + suffix)).write_text(contents.rstrip() + '\n')
            selected['compatibility'] = {
                'receipt': str((target / (name + '.json')).relative_to(FOLDER)),
                'sha256': sha(target / (name + '.json')),
                'log': str((target / (name + '-analysis.log')).relative_to(FOLDER)),
                'negative_log': str((target / (name + '-negative.log')).relative_to(FOLDER))}
            if variant == 'primary':
                entry['negative'] = {'log': selected['compatibility']['negative_log']}
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(sha(path))


if __name__ == '__main__':
    bind()
