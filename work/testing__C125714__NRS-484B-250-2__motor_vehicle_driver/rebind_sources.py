"""Bind current assignment-owned implementation into all selected constructions."""
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def main():
    folder = Path(__file__).resolve().parent
    repo = folder.parent.parent
    manifest_path = folder / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        for target in [entry] + entry.get('candidates', []):
            path = folder / target['construction']
            construction = json.loads(path.read_text(encoding='utf-8'))
            for item in construction['files']:
                source = item.get('source')
                if not source:
                    continue
                if source in (str((folder / 'scene.json').relative_to(repo)),
                              str((folder / 'config.json').relative_to(repo))):
                    case_source = folder / 'cases' / suffix / item['path']
                    if not case_source.exists():
                        case_source.write_text(item['content'], encoding='utf-8')
                    item['source'] = str(case_source.relative_to(repo))
                    source = item['source']
                item['content'] = (repo / source).read_text(encoding='utf-8')
            write(path, construction)
            target['construction_sha256'] = sha(path)
            if 'offline' in target:
                target['offline']['construction_sha256'] = target['construction_sha256']
    write(manifest_path, manifest)


if __name__ == '__main__':
    main()
