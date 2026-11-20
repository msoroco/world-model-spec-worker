"""Stage retained diagnostic sources against the ten-case draft manifest."""
import json
import shutil
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.fixture_generator import inspect
from worker_exchange.runtime_cli import materialize

MANIFEST = PACKAGE / 'draft-combined-capture-manifest.json'


def stage(case, candidate, compatibility, target):
    document = json.loads(MANIFEST.read_text())
    entry = next((row for row in document['cases'] if row['case_id'] == case), None)
    if entry is None:
        raise ValueError('Case absent from combined manifest')
    selected = entry if candidate == 'primary' else next(
        (row for row in entry['candidates'] if row['id'] == candidate), None)
    if selected is None:
        raise ValueError('Candidate absent from combined manifest')
    source, target = Path(compatibility).resolve(), Path(target).resolve()
    receipt = json.loads((source / 'compatibility.json').read_text())
    if (receipt.get('passed') is not True or receipt.get('case_id') != case or
            receipt.get('candidate_id') != candidate or
            receipt.get('construction_sha256') != selected['construction_sha256']):
        raise ValueError('Compatibility proof differs from combined candidate')
    short = case.removeprefix(PACKAGE.name + '__')
    if short in ('reference', 'contrast'):
        spec_path = PACKAGE / 'selected-diagnostics' / short / 'primary.json'
    else:
        kind, route = short.rsplit('_', 1)
        if short.startswith('employee_exception_'):
            kind, route = 'employee_exception', short.removeprefix('employee_exception_')
        spec_path = PACKAGE / 'variant-diagnostics' / kind / route / 'primary.json'
    spec = json.loads(spec_path.read_text())
    materialize(MANIFEST, case, target, candidate)
    paths = inspect(spec)
    for relative in paths:
        original, destination = source / relative, target / relative
        if not original.is_file() or destination.exists():
            raise ValueError('Diagnostic source missing or shadows construction: ' + relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, destination)
    return len(paths)
