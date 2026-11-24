"""Bind current-runtime positive and missing-source CPU proofs for six plans."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        construction = json.loads((HERE / entry['construction']).read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        needed = set(config['required_atoms']) | {
            item['name'] for item in construction['recording_description']['channels']}
        entry['acquisition'] = {
            atom: {'entrypoint': 'finalize.py' if atom not in
                   ('native_body_pose_control', 'camera_frame_join') else 'runner.py',
                   'method': 'source-joined saved Native-shaped rider, sign, body and camera diagnostic',
                   'evidence': 'rider_native_samples.jsonl, native_samples.jsonl, trace.jsonl, scenario geometry and rule packets, frame map and four original cameras; original physical designation remains pending'}
            for atom in sorted(needed)}
        for candidate_id, selected in [('primary', entry)] + [
                (candidate['id'], candidate) for candidate in entry['candidates']]:
            proof_tag = 'coverage' if suffix == 'controlled_1' else 'preflight'
            source = ROOT / '.runtime-work' / f'c104538-compat-{suffix}-{candidate_id}-{proof_tag}'
            receipt = json.loads((source / 'compatibility.json').read_text())
            if (not receipt['passed'] or receipt['case_id'] != entry['case_id'] or
                    receipt['candidate_id'] != candidate_id or
                    receipt['construction_sha256'] != selected['construction_sha256'] or
                    receipt['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256']):
                raise ValueError('Compatibility identity changed: ' + suffix + ' ' + candidate_id)
            target = HERE / 'selected-proof' / suffix / candidate_id
            target.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / 'compatibility.json', target / 'compatibility.json')
            shutil.copyfile(source / 'compatibility-analysis.log', target / 'analysis.log')
            shutil.copyfile(source / 'negative-analysis.log', target / 'negative-analysis.log')
            (target / 'compatibility-analysis.log').unlink(missing_ok=True)
            spec = {'receipt': str((target / 'compatibility.json').relative_to(HERE)),
                    'sha256': sha(target / 'compatibility.json'),
                    'log': str((target / 'analysis.log').relative_to(HERE)),
                    'negative_log': str((target / 'negative-analysis.log').relative_to(HERE))}
            selected['compatibility'] = spec
            if candidate_id == 'primary':
                entry['negative'] = {'log': spec['negative_log']}
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()
