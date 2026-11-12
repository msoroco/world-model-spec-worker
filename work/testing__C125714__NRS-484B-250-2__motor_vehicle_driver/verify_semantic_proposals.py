"""Check the C125714 draft chain against pinned stages and raw-source scope."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate  # noqa: E402


def read(path):
    return json.loads(path.read_text())


def main():
    assignment = read(REPO / 'inputs' / ROOT.name / 'assignment.json')
    manifest = read(ROOT / 'execution-manifest.json')
    result = validate(ROOT, assignment, manifest)
    proposals = read(ROOT / 'proposals/cases.json')
    assert result['selected_cases'] == len(manifest['cases']) == 8
    assert len(proposals['sweep_specs']) == 4
    assert all(spec['status'] == 'incomplete' and spec['missing_inputs']
               for spec in proposals['sweep_specs'])
    for case in proposals['cases']:
        recorded = case['recording_description']
        assert {v['name'] for v in recorded['channels']} == {'yield_control'}
        assert {v['name'] for v in recorded['context_inputs']} == {'entry_context'}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
