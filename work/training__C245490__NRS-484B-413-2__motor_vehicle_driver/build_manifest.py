"""Draft exact selected manifest for proof binding; remains partial until strict."""
import hashlib
import json
from pathlib import Path

from signal_scene import CASE_SUFFIXES


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    entries = []
    for suffix in CASE_SUFFIXES:
        case_id = HERE.name + '__' + suffix
        construction = ('construction.json' if suffix == '90' else
            f'native/selected-drafts/{suffix}/primary/construction.json')
        source = HERE / construction
        cfg = next(item['content'] for item in json.loads(source.read_text())['files']
            if item['path'] == 'config.json')
        entries.append({'case_id': case_id, 'kind': 'delivery',
            'construction': construction, 'construction_sha256': sha(source),
            'measurement_procedure': {'entrypoint': 'finalize.py',
                'output': 'analysis-report.json', 'recorded_only': True},
            'measurement_contract': 'measurement-' + suffix + '.json',
            'fixture_recipe': f'work/{HERE.name}/selected-recipe-{suffix}.json',
            'recording_description': json.loads(cfg)['recording_description'],
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
            'candidate_risk': {'status': 'physical',
                'reason': 'Original lane-transition completion may miss the target lane under the baseline lateral gain; source-bound failure trigger is required.'},
            'candidates': []})
    manifest = {'format': 'worker-execution-manifest',
        'assignment_id': HERE.name, 'status': 'draft',
        'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
        'physical_acceptance_claimed': False, 'cases': entries}
    path = HERE / 'draft-native-manifest.json'
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    return {'cases': len(entries), 'sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
