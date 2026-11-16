"""Bind fallback-specific source recipes for pinned diagnostic execution."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WITNESS = sys.argv[1] if len(sys.argv)>1 else 'reference'
if WITNESS not in ('reference','contrast'):
    raise ValueError('Unknown selected witness')
SOURCE = json.loads((ROOT / ('execution-manifest-draft.json' if WITNESS=='reference'
                           else 'execution-manifest-contrast-draft.json')).read_text())
for candidate in ('fallback1', 'fallback2', 'fallback3'):
    manifest = json.loads(json.dumps(SOURCE))
    manifest['status'] = 'draft_candidate_specific_diagnostic'
    manifest['cases'][0]['fixture_recipe'] = (
        'work/' + ROOT.name + '/selected-diagnostics/' + WITNESS + '/'
        + candidate + '-recipe.json')
    output = ROOT / ('execution-manifest-diagnostic-' + WITNESS + '-' + candidate + '.json')
    output.write_text(json.dumps(manifest, indent=2) + '\n')
    print(candidate, output)
