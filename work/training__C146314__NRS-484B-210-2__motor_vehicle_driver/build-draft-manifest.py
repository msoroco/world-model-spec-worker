"""Bind the first reference primary to the pinned CPU diagnostic interface."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WITNESS = sys.argv[1] if len(sys.argv)>1 else 'reference'
if WITNESS not in ('reference','contrast'):
    raise ValueError('Unknown selected witness')
SOURCE = ROOT / 'selected-primary' / WITNESS / 'draft-manifest.json'
TARGET = ROOT / ('execution-manifest-draft.json' if WITNESS=='reference'
                 else 'execution-manifest-contrast-draft.json')

manifest = json.loads(SOURCE.read_text())
entry = manifest['cases'][0]
construction = ROOT / 'selected-primary' / WITNESS / 'construction.json'
entry['construction'] = str(construction.relative_to(ROOT))
entry['construction_sha256'] = hashlib.sha256(construction.read_bytes()).hexdigest()
fallbacks = {
    'fallback1': ('native-raw-actors.jsonl', 'measured closing dynamics exceed reviewed bound',
                  ['lower ego and lead requested speeds']),
    'fallback2': ('overview.mkv', 'lead or lateral body edge obscured in overview',
                  ['elevate overview camera']),
    'fallback3': ('native-raw-actors.jsonl', 'observed lateral acceleration or gap oscillation exceeds reviewed bound',
                  ['lengthen lane entry distance']),
}
entry['candidates'] = []
for ident, (source, failure, knobs) in fallbacks.items():
    path = ROOT / 'selected-fallbacks' / WITNESS / ident / 'construction.json'
    entry['candidates'].append({
        'id': ident, 'construction': str(path.relative_to(ROOT)),
        'construction_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'trigger': {'source': source, 'metric': failure.split(' exceeds ')[0],
                    'failure_condition': failure},
        'changed_knobs': knobs,
    })
manifest['status'] = 'draft_first_primary_diagnostic'
TARGET.write_text(json.dumps(manifest, indent=2) + '\n')
print(TARGET)
