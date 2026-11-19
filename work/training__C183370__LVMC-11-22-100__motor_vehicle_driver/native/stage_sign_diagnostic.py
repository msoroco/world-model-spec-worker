"""Stage only inventoried sign diagnostic acquisition for saved processing."""
import json
import shutil
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.fixture_generator import inspect
from worker_exchange.runtime_cli import materialize


def stage(kind, route, compatibility, target, candidate='primary'):
    if kind not in ('warning_sign', 'highway_closed_sign') or route not in ('crossing', 'avoidance'):
        raise ValueError('Unknown sign route')
    case = PACKAGE.name + '__' + kind + '_' + route
    manifest = PACKAGE / 'draft-sign-capture-manifest.json'
    source, target = Path(compatibility).resolve(), Path(target).resolve()
    receipt = json.loads((source / 'compatibility.json').read_text())
    if (receipt.get('passed') is not True or receipt.get('candidate_id') != candidate
            or receipt.get('case_id') != case):
        raise ValueError('Compatibility proof differs from sign candidate')
    spec = json.loads((PACKAGE / 'variant-diagnostics' / kind / route / 'primary.json').read_text())
    materialize(manifest, case, target, candidate)
    for relative in inspect(spec):
        original, destination = source / relative, target / relative
        if not original.is_file() or destination.exists():
            raise ValueError('Diagnostic source missing or shadows construction: ' + relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, destination)
    return len(inspect(spec))
