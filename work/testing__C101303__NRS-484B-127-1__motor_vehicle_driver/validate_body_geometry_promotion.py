"""Replay pinned validators against the selected geometry-aware manifest."""
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path[:0] = [str(REPO / 'runtime/scenario_pipeline'), str(REPO / 'runtime')]
from scenario_pipeline.worker_exchange.execution_manifest import validate as execution_validate
from scenario_pipeline.worker_exchange.semantic_delivery import validate as semantic_validate
from scenario_pipeline.worker_exchange.physical_preparation import validate as physical_validate
from scenario_pipeline.worker_exchange.package_compatibility import check_receipts


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    selected_path = ROOT / 'execution-manifest.json'
    candidate_path = ROOT / 'body-geometry-draft/promotion-candidate.json'
    if digest(selected_path) != digest(candidate_path):
        raise ValueError('Selected manifest differs from proved promotion candidate')
    manifest = execution_validate(REPO, ROOT.name)
    if len(manifest['cases']) != 8:
        raise ValueError('Expected eight selected cases')
    assignment = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
    semantic_validate(ROOT, assignment, manifest)
    check_receipts(REPO, ROOT, manifest)
    for case in manifest['cases']:
        physical_validate(REPO, ROOT, case)
        for row in [case] + case['candidates']:
            bundle = json.loads((ROOT / row['construction']).read_text())
            runner = next(file['content'] for file in bundle['files']
                          if file['path'] == 'runner.py')
            if ("target_center_spacing_m=config['requested_engineering_gap_m']+native_body_offset("
                    not in runner or
                    "target_center_spacing_m=config['requested_engineering_gap_m']+4"
                    in runner):
                raise ValueError('Selected runner lacks Native body geometry: '
                                 + case['case_id'])
        print(case['case_id'], 'selected proof bindings passed')
    print('all selected geometry-aware proofs validated')


if __name__ == '__main__':
    main()
