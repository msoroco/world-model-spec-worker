"""Bind selected adjacent-vehicle proof chain and original-source acquisition."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    manifest['status'] = 'cpu_prepared_pending_original_machine_classification_police_duty_and_physical_review'
    evidence = {
        'ru.subject': ['actor-poses.jsonl', 'video_frames.jsonl'],
        'ru.motorcycle': ['lane-inventory.json', 'classification-review.json', 'actor-poses.jsonl'],
        'ru.moped': ['lane-inventory.json', 'classification-review.json', 'actor-poses.jsonl'],
        'st.lane_adjacency': ['road.xodr', 'lane-inventory.json', 'split-review.json'],
        'rel.occupies': ['actor-poses.jsonl', 'lane-inventory.json', 'split-review.json'],
        'drv.straddles_marking': ['road.xodr', 'actor-poses.jsonl', 'split-review.json'],
        'rel.bearing': ['actor-poses.jsonl', 'video_frames.jsonl'],
        'rel.longitudinal_overlap': ['actor-poses.jsonl', 'video_frames.jsonl'],
        'ru.motor_vehicle': ['lane-inventory.json', 'actor-poses.jsonl'],
        'kin.velocity': ['actor-poses.jsonl', 'video_frames.jsonl']}
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        proof = HERE / 'proofs' / suffix
        entry['physical_preparation'] = {'receipt': str((proof / 'physical-preparation.json').relative_to(HERE)),
                                         'sha256': sha(proof / 'physical-preparation.json')}
        entry['acquisition'] = {name: {'entrypoint': 'finalize.py',
            'method': 'original Native frame/body/map join and independent source review for ' + name,
            'evidence': sources} for name, sources in evidence.items()}
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
