"""Recheck all nine exact CPU delivery contracts together."""
import json
from pathlib import Path

from worker_exchange import delivery_handoff, execution_manifest, package_compatibility, semantic_delivery

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
IDENT = ROOT.name
manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
assignment = json.loads((REPO / 'inputs' / IDENT / 'assignment.json').read_text())
execution_manifest.validate(REPO, IDENT)
for entry in manifest['cases']:
    delivery_handoff.validate_case(ROOT, entry, expected_sets=('held-out',))
package_compatibility.check_receipts(REPO, ROOT, manifest)
semantic = semantic_delivery.validate(ROOT, assignment, manifest)
assert semantic['selected_cases'] == 9
print('Nine exact execution, independent delivery, compatibility and semantic contracts pass')
