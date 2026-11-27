"""Read-only full queue/catalog dispatch and canonical CLI shape audit."""
import hashlib
import importlib.util
import json
import shlex
import sys
from pathlib import Path

sys.dont_write_bytecode = True
root = Path(__file__).resolve().parents[2]
shared = root / 'work/_shared'
spec = importlib.util.spec_from_file_location('queue_dispatch', shared / 'queue_dispatch.py')
dispatch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch)
queue_bytes = (shared / 'gpu-queue.json').read_bytes()
queue = json.loads(queue_bytes)
checks = 0
errors = []
seen = set()
wrapped = 0

def unwrap(value, identifier, stage, candidate=None):
    global checks, wrapped
    tokens = shlex.split(value)
    if 'work/_shared/queue_dispatch.py' not in tokens:
        return value
    expected = ['.venv-cpu/bin/python', 'work/_shared/queue_dispatch.py', identifier, stage]
    if candidate is not None:
        expected.append(candidate)
    if tokens != expected:
        errors.append('bad dispatch wrapper ' + identifier + ' ' + stage)
        return value
    try:
        resolved = dispatch.resolve(identifier, stage, candidate)
    except (KeyError, ValueError) as error:
        errors.append('missing catalog command ' + identifier + ' ' + str(error))
        return value
    wrapped += 1
    checks += 1
    return resolved

for row in queue['cases']:
    aid, cid = row['assignment_id'], row['case_id']
    if cid in seen:
        errors.append('duplicate case ' + cid)
    seen.add(cid)
    for stage in dispatch.STAGES:
        if stage not in row:
            continue
        command = unwrap(row[stage], cid, stage)
        shlex.split(command)
        checks += 1
    for candidate, wrapper in row['candidate_commands'].items():
        command = unwrap(wrapper, cid, 'prepare-delivery', candidate)
        tokens = shlex.split(command)
        if 'prepare-delivery' not in tokens or '--candidate' not in tokens or tokens[tokens.index('--candidate') + 1] != candidate:
            errors.append('wrong candidate command ' + cid + ' ' + candidate)
        checks += 1
    for stage in ('prepare-delivery', 'execute-delivery', 'accept-delivery'):
        tokens = shlex.split(unwrap(row[dispatch.STAGES[stage]], cid, stage))
        if stage not in tokens or '--assignment' not in tokens or tokens[tokens.index('--assignment') + 1] != aid or '--case' not in tokens or tokens[tokens.index('--case') + 1] != cid:
            errors.append('wrong canonical identity ' + cid + ' ' + stage)
        if stage == 'accept-delivery' and ('--review-archive' not in tokens or tokens[tokens.index('--review-archive') + 1] != '/external/archive'):
            errors.append('missing external review archive ' + cid)
        checks += 1
for row in queue['comparison_audit_commands']:
    key = row['assignment_id'] + '::' + row['comparison_id']
    if key in seen:
        errors.append('duplicate comparison ' + key)
    seen.add(key)
    command = unwrap(row['command'], key, 'comparison')
    shlex.split(command)
    checks += 1
result = {'format': 'worker-queue-catalog-static-audit',
          'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'queue_sha256': hashlib.sha256(queue_bytes).hexdigest(),
          'assignments': len(queue['assignments']), 'cases': len(queue['cases']),
          'comparisons': len(queue['comparison_audit_commands']),
          'checks': checks, 'wrapped': wrapped, 'errors': errors, 'passed': not errors,
          'limit': 'Static command identity and dispatch check; no local DB, CARLA execution, source audit or acceptance performed.'}
print(json.dumps(result, indent=2))
raise SystemExit(1 if errors else 0)
