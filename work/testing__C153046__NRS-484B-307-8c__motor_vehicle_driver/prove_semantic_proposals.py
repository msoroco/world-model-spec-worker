"""Run pinned canonical stage chain checks on the draft proposals."""
from __future__ import annotations

import json
import os
from pathlib import Path
import hashlib
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
if not os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT'):
    raise RuntimeError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime imports')
sys.path.insert(0, str(ROOT.parent.parent / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate

assignment = json.loads((ROOT.parent.parent / 'inputs' / ROOT.name / 'assignment.json').read_text())
manifest = json.loads((ROOT / 'execution-manifest.draft.json').read_text())
print(json.dumps(validate(ROOT, assignment, manifest), sort_keys=True))


def expect_rejection(folder: Path, expected: str) -> None:
    try:
        validate(folder, assignment, manifest)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(f'unexpected rejection: {error}') from error
        print('rejected:', expected)
    else:
        raise AssertionError(f'semantic validator accepted {expected}')


private = ROOT.parent.parent / '.runtime-work'
private.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='c153046-semantic-negative-', dir=private) as temporary:
    folder = Path(temporary)
    shutil.copytree(ROOT / 'proposals', folder / 'proposals')
    shutil.copytree(ROOT / 'constructions', folder / 'constructions')
    template = folder / 'proposals/template.json'
    template.write_text(template.read_text().replace('yield the right-of-way', 'skip the right-of-way'))
    expect_rejection(folder, 'Stage proposal source hash changed')

    shutil.copytree(ROOT / 'proposals', folder / 'proposals', dirs_exist_ok=True)
    case_path = folder / 'proposals/cases.json'
    cases = json.loads(case_path.read_text())
    cases['cases'][1]['recording_description']['channels'][0]['method'] = 'changed source channel'
    case_path.write_text(json.dumps(cases, indent=2) + '\n')
    index_path = folder / 'proposals/semantic-index.json'
    index = json.loads(index_path.read_text())
    index['stages']['cases']['sha256'] = hashlib.sha256(case_path.read_bytes()).hexdigest()
    index_path.write_text(json.dumps(index, indent=2) + '\n')
    expect_rejection(folder, 'Canonical case changed the recording description')
