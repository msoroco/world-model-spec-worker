"""Remove unsupported Core demands while retaining selected source measurements."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / 'execution-manifest.json'
UNSUPPORTED = {'ru.electric_bicycle', 'ru.electric_scooter', 'ru.vehicle'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    changed = []
    for case in manifest['cases']:
        for candidate in [case] + case['candidates']:
            path = ROOT / candidate['construction']
            construction = json.loads(path.read_text())
            file = next(row for row in construction['files'] if row['path'] == 'config.json')
            config = json.loads(file['content'])
            removed = UNSUPPORTED.intersection(config.get('required_atoms', []))
            if not removed:
                continue
            config['required_atoms'] = [atom for atom in config['required_atoms']
                                        if atom not in UNSUPPORTED]
            file['content'] = json.dumps(config, indent=2, sort_keys=True) + '\n'
            path.write_text(json.dumps(construction, indent=2, sort_keys=True) + '\n')
            candidate['construction_sha256'] = digest(path)
            changed.append((case['case_id'].removeprefix(ROOT.name + '__'),
                            candidate.get('id', 'primary'), sorted(removed)))
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    for case, ident, removed in changed:
        print(case, ident, ','.join(removed))
    print('Changed construction count:', len(changed))


if __name__ == '__main__':
    main()
