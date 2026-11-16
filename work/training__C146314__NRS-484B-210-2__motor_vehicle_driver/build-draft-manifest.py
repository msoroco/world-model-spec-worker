"""Bind the first reference primary to the pinned CPU diagnostic interface."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'selected-primary/reference/draft-manifest.json'
TARGET = ROOT / 'execution-manifest-draft.json'

manifest = json.loads(SOURCE.read_text())
entry = manifest['cases'][0]
construction = ROOT / 'selected-primary/reference/construction.json'
entry['construction'] = str(construction.relative_to(ROOT))
entry['construction_sha256'] = hashlib.sha256(construction.read_bytes()).hexdigest()
manifest['status'] = 'draft_first_primary_diagnostic'
TARGET.write_text(json.dumps(manifest, indent=2) + '\n')
print(TARGET)
