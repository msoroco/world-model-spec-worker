"""Build a source-hashed alternate spawn position for each exact case."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        construction = json.loads((HERE / entry['construction']).read_text())
        runner = next(item for item in construction['files'] if item['path'] == 'runner.py')
        original = 'carla.Location(x=0, y=-5, z=.5)'
        assert runner['content'].count(original) == 1
        runner['content'] = runner['content'].replace(original,
            'carla.Location(x=0, y=-6.5, z=.5)')
        construction['status'] = 'alternate_native_spawn_diagnostic'
        output = HERE / 'v2-fallback1' / suffix / 'construction.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(construction, indent=2) + '\n')
        entry['candidates'] = [{
            'id': 'fallback1', 'construction': str(output.relative_to(HERE)),
            'construction_sha256': sha(output),
            'trigger': {'source': 'original_native_spawn_result',
                        'metric': 'try_spawn_actor_returned_none',
                        'failure_condition': 'Native walker spawn at primary (-5 m) fails or overlaps an authored fixture'},
            'changed_knobs': ['walker spawn y=-6.5 m; 1.5 m additional approach clearance'],
        }]
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'fallback_cases': len(manifest['cases'])}))


if __name__ == '__main__':
    main()
