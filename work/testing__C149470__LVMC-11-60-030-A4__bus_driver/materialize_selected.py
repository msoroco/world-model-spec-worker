"""Return exact selected constructions and configs for local review."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    for index, entry in enumerate(manifest['cases']):
        name = entry['case_id'].removeprefix(HERE.name + '__')
        construction = HERE / entry['construction']
        value = json.loads(construction.read_text())
        config = next(item['content'] for item in value['files']
                      if item['path'] == 'config.json')
        folder = HERE / 'cases' / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'construction.json').write_bytes(construction.read_bytes())
        (folder / 'config.json').write_text(config, encoding='utf-8')
        if index == 0:
            (HERE / 'construction.json').write_bytes(construction.read_bytes())
            (HERE / 'config.json').write_text(config, encoding='utf-8')
        for candidate in entry.get('candidates', []):
            destination = folder / candidate['id']
            destination.mkdir(parents=True, exist_ok=True)
            (destination / 'construction.json').write_bytes((HERE / candidate['construction']).read_bytes())
    print('materialized selected constructions:', len(manifest['cases']))


if __name__ == '__main__':
    main()
