"""Keep returned proof filenames outside generated-directory name prefixes."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def renamed(value):
    path = Path(value)
    name = path.name
    if name.startswith(('offline-', 'compatibility-')):
        return str(path.with_name('proof-' + name))
    return value


def main():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for path in sorted(ROOT.rglob('*')):
        if path.is_file() and path.name.startswith(('offline-', 'compatibility-')):
            path.rename(path.with_name('proof-' + path.name))
    for entry in manifest['cases']:
        for target in (entry, *entry.get('candidates', [])):
            if target.get('offline', {}).get('log'):
                target['offline']['log'] = renamed(target['offline']['log'])
            for key in ('receipt', 'log', 'negative_log'):
                if target.get('compatibility', {}).get(key):
                    target['compatibility'][key] = renamed(target['compatibility'][key])
        if entry.get('negative', {}).get('log'):
            entry['negative']['log'] = renamed(entry['negative']['log'])
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    print('normalized returned proof path prefixes')


if __name__ == '__main__':
    main()
