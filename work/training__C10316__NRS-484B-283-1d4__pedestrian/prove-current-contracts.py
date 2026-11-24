"""Pin the four draft measurement contracts to the current v2 schema."""
import hashlib
import json
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if not Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve().is_relative_to(
        (ROOT / '.runtime-work').resolve()):
    raise RuntimeError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import validate


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


plan = json.loads((HERE / 'case-plan.json').read_text())
rows = []
for suffix in ('witness_1', 'witness_2', 'exception_1_1', 'exception_1_2'):
    group = 'draft-steady' if suffix.startswith('witness') else 'draft-exception'
    bundles = 'draft-bundles' if suffix.startswith('witness') else 'draft-exception-bundles'
    source = HERE / group / suffix / 'measurement-contract.json'
    construction = HERE / bundles / suffix / 'primary/construction.json'
    contract = json.loads(source.read_text())
    contract['format'] = 'worker-measurement-contract'
    target = HERE / 'current-contracts' / (suffix + '.json')
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(contract, indent=2) + '\n')
    bundle = json.loads(construction.read_text())
    code = next(item['content'] for item in bundle['files'] if item['path'] == 'finalize.py')
    validate(contract, plan['requirement_dispositions'], code, contract['case_id'])
    rows.append({'case_id': contract['case_id'], 'legacy_contract_sha256': sha(source),
                 'current_contract_sha256': sha(target),
                 'construction_sha256': sha(construction),
                 'requirement_count': len(contract['requirements'])})
proof = {'format': 'c10316-current-contract-schema-proof-v1', 'passed': True,
         'scope': 'unselected draft schema and method binding; no v2 package compatibility',
         'cases': rows}
(HERE / 'current-contracts-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
print(json.dumps(proof, indent=2))
