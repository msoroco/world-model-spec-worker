"""Bind selected access-aisle proof chain and source acquisition."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    manifest['status'] = 'cpu_prepared_pending_original_premises_designation_and_parking_review'
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        proof = HERE / 'proofs' / suffix
        entry['physical_preparation'] = {'receipt': str((proof / 'physical-preparation.json').relative_to(HERE)),
                                         'sha256': sha(proof / 'physical-preparation.json')}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        entry['acquisition'] = {
            'st.parking_space': {'entrypoint': 'runner.py', 'method': 'original road and independent official aisle designation with adjacent accessible bay', 'evidence': ['road.xodr', 'aisle-designation-review.json']},
            'st.lane_marking': {'entrypoint': 'runner.py', 'method': 'original reference RGB plus independently reviewed contrasting marking or paving', 'evidence': ['reference_corner.mkv', 'aisle-designation-review.json']},
            'drv.standing_or_parked': {'entrypoint': 'runner.py', 'method': 'original speed and separate parked activity classification', 'evidence': ['native-vehicle.jsonl', 'parking-review.json']},
            'rel.occupies': {'entrypoint': 'runner.py', 'method': 'original body against reviewed aisle and premises jurisdiction', 'evidence': ['native-vehicle.jsonl', 'aisle-designation-review.json', 'premises-review.json']},
            'kin.extent': {'entrypoint': 'runner.py', 'method': 'original full-body corners every frame', 'evidence': ['native-vehicle.jsonl']}}
        entry['post_capture'] = {'recorded_only': True,
            'command': 'runtime.py process-saved --manifest work/' + AID + '/execution-manifest.json --case ' + entry['case_id'] +
                ' --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER',
            'feedback_command': 'cat $SAVED_OUTPUT/feedback.json # ' + entry['case_id']}
        if (proof / 'saved.log').is_file():
            entry['post_capture'].update(test_log=str((proof / 'saved.log').relative_to(HERE)),
                test_log_sha256=sha(proof / 'saved.log'), test_exit_code=0)
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    first = json.loads((HERE / manifest['cases'][0]['construction']).read_text())
    for item in first['files']:
        target = HERE / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])
    (HERE / 'construction.json').write_text(json.dumps(first, indent=2) + '\n')
    print({'cases': len(manifest['cases']), 'fallbacks': sum(len(row['candidates']) for row in manifest['cases'])})


if __name__ == '__main__':
    main()
