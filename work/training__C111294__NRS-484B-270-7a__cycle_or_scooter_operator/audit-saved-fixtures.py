"""Independent audit of the saved bicycle/motorist diagnostic pair."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / '.runtime-work/c111294-saved-fixtures'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    seen = {}
    for suffix, expected_brakes in (('witness_1', 0), ('witness_2', 175)):
        folder = BASE / (suffix + '-positive')
        source = json.loads((folder / 'interaction.json').read_text())
        manifest = json.loads((folder / 'capture/manifest.json').read_text())
        report = json.loads((folder / 'analysis-report.json').read_text())
        result = json.loads((folder / 'result.json').read_text())
        frames = source['frames']
        assert len(frames) == 480
        assert manifest['sources']['interaction.json'] == sha(folder / 'interaction.json')
        assert all(row['frame'] == i and row['video_frame'] == i and
                   row['native_frame'] == i for i, row in enumerate(frames))
        assert all(row['bicycle']['class'] == 'human_powered_bicycle' and
                   row['motor_vehicle']['class'] == 'motor_vehicle' and
                   row['bicycle']['actor_id'] != row['motor_vehicle']['actor_id'] for row in frames)
        brakes = sum(row['motor_vehicle']['brake_applied'] is True for row in frames)
        assert brakes == expected_brakes
        value = report['measurements']['bicycle_motorist_interaction']['value']
        assert value['motor_braking_frames'] == brakes
        assert value['source_sha256'] == sha(folder / 'interaction.json')
        assert not value['intent_physically_verified'] and not value['legal_interference_claimed']
        assert result['target_checks'][0]['matched'] and not result['accepted']
        assert not (BASE / (suffix + '-negative/interaction.json')).exists()
        assert not (BASE / (suffix + '-negative/result.json')).exists()
        seen[suffix] = {'source_sha256': sha(folder / 'interaction.json'),
                        'braking_frames': brakes, 'report_sha256': sha(folder / 'analysis-report.json')}
    assert frames[0]['motor_vehicle']['actor_id'] == 202
    assert seen['witness_1']['braking_frames'] != seen['witness_2']['braking_frames']
    return {'passed': True, 'cases': seen, 'independent_saved_source_checks': True,
            'scope': 'synthetic CPU diagnostic; no physical behavior or acceptance'}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
