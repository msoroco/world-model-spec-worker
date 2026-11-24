"""Independently bind 30-second draft constructions, logs, and source proofs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    manifest_path = HERE / 'duration-probes/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    proof_path = HERE / 'duration-probes/source-measurement-proof.json'
    proof = json.loads(proof_path.read_text())
    require(manifest['status'] == 'draft_not_selected' and len(manifest['cases']) == 2,
            'Unselected pair missing')
    require(proof['frames'] == 600 and len(proof['results']) == 2, 'Source proof incomplete')
    retained = Path(proof['retained_root'])
    reviewed = []
    common = None
    for entry, record in zip(manifest['cases'], proof['results']):
        case_id = entry['case_id']
        suffix = case_id.rsplit('__', 1)[-1]
        require(record['case_id'] == case_id, 'Case/proof differs')
        construction_path = HERE / 'duration-probes' / entry['construction']
        require(sha(construction_path) == entry['construction_sha256'] == record['construction_sha256'],
                'Construction hash differs')
        construction = json.loads(construction_path.read_text())
        files = {row['path']: row['content'] for row in construction['files']}
        config = json.loads(files['config.json'])
        require((config['duration_s'], config['rate_hz']) == (30, 20), 'Duration differs')
        require([x['name'] for x in config['cameras']] ==
                ['overview', 'vehicle_approach', 'curb_side', 'curb_close'], 'Cameras differ')
        require('FRAMES = 600' in files['runner.py'] and 'len(rows) != 600' in files['curb.py']
                and 'count != 600' in files['finalize.py'], 'Embedded 600-frame paths absent')
        require(hashlib.sha256(files['curb.py'].encode()).hexdigest() ==
                record['measurement_source_sha256'], 'Measurement source differs')
        folder = retained / suffix
        for name, digest in record['source_hashes'].items():
            require(sha(folder / name) == digest, 'Raw source hash differs: ' + name)
        require(not record['driver_capability_measured'] and not record['legal_verdict_claimed'],
                'Unsupported physical or legal claim')
        require([x['label'] for x in record['negative_rejections']] ==
                ['missing-final-frame', 'wrong-footprint'], 'Negative proof missing')
        log = HERE / 'duration-probes' / suffix / 'offline.log'
        lines = log.read_text().splitlines()
        outcome = json.loads(lines[0])
        require(outcome['frames'] == 600 and len(outcome['cameras']) == 4 and
                not outcome['native_imported'] and not outcome['impossibility_to_yield_proven'] and
                lines[-1] == 'OK', 'Offline proof invalid')
        fixed = {k: v for k, v in config.items() if k not in ('case_id', 'selected_case_id', 'case_suffix', 'case', 'candidate_id')}
        if common is None:
            common = fixed
        else:
            require(fixed == common, 'Controlled pair changed common configuration')
        reviewed.append({'case_id': case_id, 'construction_sha256': sha(construction_path),
                         'offline_log_sha256': sha(log),
                         'source_sha256': record['source_hashes'],
                         'conditional_relation': record['conditional_yield_relation']})
    require([x['conditional_relation'] for x in reviewed] ==
            ['conditional_yield_possible', 'conditional_yield_impossible'],
            'Controlled relation missing')
    output = {'format': 'c230222-duration-independent-audit-v1',
              'passed': True, 'manifest_sha256': sha(manifest_path),
              'measurement_proof_sha256': sha(proof_path), 'reviewed': reviewed,
              'physical_yield_proven': False, 'legal_verdict_claimed': False}
    target = HERE / 'duration-probes/independent-audit.json'
    target.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'reviewed': len(reviewed), 'passed': True}))


if __name__ == '__main__':
    main()
