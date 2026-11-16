"""Join the two exact selected cases without claiming delivery readiness."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
reference=json.loads((ROOT/'execution-manifest-draft.json').read_text())
contrast=json.loads((ROOT/'execution-manifest-contrast-draft.json').read_text())
reference['cases'].extend(contrast['cases'])
reference['status']='draft_unified_selected_cases'
reference['delivery_ready']=False
target=ROOT/'execution-manifest-unified-draft.json'
target.write_text(json.dumps(reference,indent=2)+'\n')
print(target, len(reference['cases']))
