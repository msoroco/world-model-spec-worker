"""Verify a candidate source change is rejected, restoring the CPU fixture afterward."""
import json
import subprocess
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parent.parent
receipt = json.loads((folder / 'fallback-candidate-source-receipt.json').read_text())
selected = next(row for row in receipt['sources'] if row['case_id'].endswith('source_verified_closer')
                and row['candidate_id'] == 'fallback1')
path = repo / selected['path']
original = path.read_bytes()
rows = path.read_text().splitlines()
first = json.loads(rows[0])
first['diagnostic_projection']['construction_sha256'] = 'changed-source'
rows[0] = json.dumps(first, separators=(',', ':'))
try:
    path.write_text('\n'.join(rows) + '\n')
    command = [str(repo / '.venv-cpu/bin/python'), str(folder / 'full_duration_fallback_comparison_proof.py')]
    rejected = subprocess.run(command, cwd=repo, capture_output=True, text=True)
finally:
    path.write_bytes(original)
if rejected.returncode == 0 or 'Fallback projection source changed' not in rejected.stderr:
    raise ValueError('Changed fallback source was accepted')
print(json.dumps({'negative': 'changed_candidate_source', 'rejected': True,
                  'source_restored': path.read_bytes() == original,
                  'physical_acceptance_claimed': False}))
