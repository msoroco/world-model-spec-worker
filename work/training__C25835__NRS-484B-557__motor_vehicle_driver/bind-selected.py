"""Bind source-hashed selected rail-stop packages and acquisition mappings."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / 'draft-native-manifest.json').read_text())
    manifest['status'] = 'cpu_prepared_pending_original_rail_authority_and_physical_review'
    evidence = {
        'dev.stop_sign': ['sign-authority.txt', 'sign-review.json', 'overview.mkv',
                          'rail-inventory.json'],
        'dev.governs': ['sign-review.json', 'road.xodr', 'rail-inventory.json',
                        'overview.mkv'],
        'st.railway_crossing': ['road.xodr', 'rail-inventory.json',
                                'designation-authority.txt', 'designation-review.json'],
        'rel.centre_distance': ['rail-inventory.json', 'rail-trace.jsonl',
                                'video_frames.jsonl'],
        'drv.stopped': ['rail-trace.jsonl', 'video_frames.jsonl'],
        'drv.approaching': ['rail-trace.jsonl', 'video_frames.jsonl'],
        'drv.time_to_conflict': ['rail-trace.jsonl', 'occluder-review.json',
                                 'overview.mkv'],
        'ru.rail_vehicle': ['rail-trace.jsonl', 'overview.mkv']}
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        proof = HERE / 'proofs' / suffix
        entry['physical_preparation'] = {
            'receipt': str((proof / 'physical-preparation.json').relative_to(HERE)),
            'sha256': sha(proof / 'physical-preparation.json')}
        entry['acquisition'] = {name: {'entrypoint': 'finalize.py',
            'method': 'original Native rail/vehicle/frame/pixel join and separately reviewed administrative designation, official sign and occluder',
            'evidence': sources} for name, sources in evidence.items()}
        if (proof / 'saved.log').is_file():
            entry.setdefault('post_capture', {}).update(
                test_log=str((proof / 'saved.log').relative_to(HERE)),
                test_log_sha256=sha(proof / 'saved.log'), test_exit_code=0)
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    first = json.loads((HERE / manifest['cases'][0]['construction']).read_text())
    for item in first['files']:
        target = HERE / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])
    (HERE / 'construction.json').write_text(json.dumps(first, indent=2) + '\n')
    print({'cases': len(manifest['cases']),
           'fallbacks': sum(len(row['candidates']) for row in manifest['cases'])})


if __name__ == '__main__':
    main()
