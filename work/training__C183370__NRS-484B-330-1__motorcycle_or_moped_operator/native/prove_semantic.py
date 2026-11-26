"""Validate draft semantic stages against the pinned canonical stage contracts."""

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / 'runtime'), str(REPO / 'runtime/scenario_pipeline')]
from scenario_pipeline.worker_exchange.semantic_delivery import validate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assignment = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
    manifest = json.loads((ROOT / 'draft-native-manifest.json').read_text())
    result = validate(ROOT, assignment, manifest)
    scratch = REPO / '.runtime-work/c183370-semantic-output'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch, prefix='negative-') as temporary:
        damaged = Path(temporary)
        shutil.copytree(ROOT / 'proposals', damaged / 'proposals')
        (damaged / 'native').mkdir()
        for entry in manifest['cases']:
            source = ROOT / entry['construction']
            shutil.copy2(source, damaged / entry['construction'])
        relevance = damaged / 'proposals/relevance.json'
        relevance.write_text(relevance.read_text().replace('specific_match', 'general_match', 1))
        try:
            validate(damaged, assignment, manifest)
        except ValueError as error:
            if 'Stage proposal source hash changed' not in str(error):
                raise
        else:
            raise AssertionError('Changed source-hashed semantic stage accepted')
    proof = {
        'format': 'c183370-draft-semantic-cpu-proof-v1',
        'assignment_id': ROOT.name,
        'status': 'validated_draft_unselected',
        'stage_count': result['stage_count'],
        'case_count': result['selected_cases'],
        'changed_stage_rejections': 1,
        'semantic_index_sha256': result['index_sha256'],
        'draft_manifest_sha256': sha(ROOT / 'draft-native-manifest.json'),
        'source_assignment_sha256': sha(REPO / 'inputs' / ROOT.name / 'assignment.json'),
        'physical_original_review_complete': False,
        'delivery_ready': False,
    }
    (ROOT / 'native/semantic-cpu-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'stage_count': result['stage_count'], 'case_count': result['selected_cases']}))


if __name__ == '__main__':
    main()
