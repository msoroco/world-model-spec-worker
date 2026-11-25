"""Build paired upstream-spawn fallbacks for a measured stop-margin failure."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'batch.json').is_file())
OLD = 'THROUGH_START_AUTHORED_Y_M = 65.0'
NEW = 'THROUGH_START_AUTHORED_Y_M = 70.0'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


source_manifest = json.loads((HERE / 'draft-primary-manifest.json').read_text())
entries = []
for case_no, folder in ((1, 'draft-primary'), (2, 'draft-controlled')):
    construction = json.loads((HERE / folder / 'construction.json').read_text())
    files = construction['files']
    live = next(item for item in files if item['path'] == 'live_capture.py')
    if live['content'].count(OLD) != 1:
        raise ValueError('Expected exactly one current Native through start')
    live['content'] = live['content'].replace(OLD, NEW)
    construction['fallback_purpose'] = 'Move the same through route start 5 m upstream if source motion overshoots the first yield hold before the entrant clears.'
    construction['fallback_changed_knobs'] = ['through_start_authored_y_m']
    path = HERE / 'cases' / f'probe_{case_no}' / 'fallback1' / 'construction.json'
    write(path, construction)
    entry = dict(source_manifest['cases'][case_no - 1])
    entry['construction'] = path.relative_to(HERE).as_posix()
    entry['construction_sha256'] = sha(path)
    entry['candidate_risk'] = {'status': 'none', 'reason': 'Single exact fallback offline proof only; selected manifest pending.'}
    entry['candidates'] = []
    entries.append(entry)
fallback_manifest = dict(source_manifest, cases=entries,
                         status='unselected_physical_fallback_offline')
manifest_path = HERE / 'fallback-offline-manifest.json'
write(manifest_path, fallback_manifest)
print(json.dumps({'manifest_sha256': sha(manifest_path),
                  'fallback_construction_sha256': [entry['construction_sha256'] for entry in entries],
                  'changed_knobs': ['through_start_authored_y_m']}, sort_keys=True))
