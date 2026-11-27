"""Bind exact selected constructions before offline CPU proof."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def build() -> None:
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    entries = []
    for case in plan['cases']:
        suffix = case['case_id'].split('__')[-1]
        source = ROOT / 'cases' / suffix / 'construction.json'
        entries.append({'case_id': case['case_id'], 'kind': 'delivery',
                        'construction': str(source.relative_to(ROOT)),
                        'construction_sha256': sha(source),
                        'fixture_recipe': str((ROOT / 'cases' / suffix / 'fixture-recipe.json').relative_to(REPO)),
                        'measurement_contract': f'cases/{suffix}/measurement-contract.json',
                        'measurement_procedure': {'entrypoint': 'analysis.py'},
                        'candidate_risk': {'status': 'none', 'reason': 'No specific Native failure diagnosed in CPU geometry/interval checks; original stop occupancy and camera coverage require local validation.'},
                        'candidates': [],
                        'native_handoff': {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}})
    manifest = {'format': 'worker-execution-manifest-draft',
                'assignment_id': ROOT.name,
                'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'cases': entries}
    (ROOT / 'execution-manifest.draft.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print('six construction-hashed draft cases')

if __name__ == '__main__':
    build()
