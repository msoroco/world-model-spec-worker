"""Build two controlled same-lane Native drafts from authored sources."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2).rstrip() + '\n')


def main():
    subprocess.run([sys.executable, '-B', str(ROOT / 'build-draft.py')], check=True)
    source = ROOT / 'draft-same-lane/controlled_2/primary/construction.json'
    passing = json.loads(source.read_text())
    prefix = ROOT.name
    follow_id = prefix + '__controlled_1'
    following = json.loads(json.dumps(passing))
    following['case_id'] = follow_id
    following['measurement_plan']['entrypoint'] = 'finalize.py'
    following['mechanisms'] = [
        'motorcycle and car both target 3 m/s with original 30 m body separation',
        'both complete bodies remain within the same one-way traffic lane',
        'source-bound measurement rejects any longitudinal overlap',
    ]
    following['static_checks'].append('following body gap remains positive for all 600 frames')
    for item in following['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config['case_id'] = follow_id
            config['selected_case_id'] = follow_id
            config['supported_case_ids'] = [follow_id, prefix + '__controlled_2']
            config['case_suffix'] = 'controlled_1'
            config['case'] = {'case_id': follow_id}
            config['physical_target'] = {'behavior': 'same-lane following without overlap'}
            config['status'] = 'selected_cpu_draft_not_delivery_prepared'
            item['content'] = json.dumps(config, indent=2) + '\n'
    target = ROOT / 'draft-same-lane/controlled_1/primary/construction.json'
    write(target, following)
    batch = json.loads((REPO / 'batch.json').read_text())
    entries = []
    for case_id, path, procedure in (
        (follow_id, target, 'finalize.py'),
        (prefix + '__controlled_2', source, 'finalize.py'),
    ):
        entries.append({'case_id': case_id, 'kind': 'delivery',
                        'construction': str(path.relative_to(ROOT)),
                        'construction_sha256': sha(path),
                        'candidate_risk': {
                            'status': 'none',
                            'reason': 'No independently justified alternate physical knob within the exact frozen one-way lane, actor pair and source-bound capture; original Native feasibility remains subject to local review'},
                        'candidates': [], 'measurement_procedure': {'entrypoint': procedure},
                        'delivery_readiness': 'incomplete'})
    manifest = {'format': 'worker-selected-cpu-draft-manifest-v1',
                'assignment_id': ROOT.name,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'partial', 'cases': entries}
    write(ROOT / 'draft-two-case-manifest.json', manifest)
    print(json.dumps({'cases': [entry['case_id'] for entry in entries],
                      'construction_sha256': [entry['construction_sha256'] for entry in entries]}))


if __name__ == '__main__':
    main()
