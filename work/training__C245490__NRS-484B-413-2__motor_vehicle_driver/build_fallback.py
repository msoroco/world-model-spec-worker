"""Build same-case alternate lateral gain without changing capture or law scope."""
import hashlib
import json
from pathlib import Path

from signal_scene import CASE_SUFFIXES

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = []
    for suffix in CASE_SUFFIXES:
        primary = HERE / ('construction.json' if suffix == '90' else
            'native/selected-drafts/' + suffix + '/primary/construction.json')
        construction = json.loads(primary.read_text())
        config_file = next(item for item in construction['files'] if item['path'] == 'config.json')
        cfg = json.loads(config_file['content'])
        cfg['controller_gain'] = 2.0
        folder = HERE / 'native/selected-drafts' / suffix / 'fallback1'
        cfg_path = folder / 'config.json'
        put(cfg_path, cfg)
        config_file['content'] = cfg_path.read_text()
        config_file['source'] = str(cfg_path.relative_to(REPO))
        construction['candidate_id'] = 'fallback1'
        construction['mechanisms'].append('alternate lateral gain 2.0 versus primary 1.5')
        path = folder / 'construction.json'
        put(path, construction)
        out.append({'suffix': suffix, 'construction': str(path.relative_to(HERE)),
                    'construction_sha256': sha(path)})
    return out


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
