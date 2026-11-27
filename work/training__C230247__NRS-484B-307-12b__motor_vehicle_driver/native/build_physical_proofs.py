"""Prove measured engineering motion met/not-met/missing-evidence CPU branches."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest_path = FOLDER/'draft-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    proof_root = REPO/'.runtime-work'/'c230247-12b-physical-proofs-v4'
    proof_root.mkdir(parents=True, exist_ok=True)
    for entry in manifest['cases']:
        condition = entry['case_id'].rsplit('__',1)[-1]
        source = REPO/'.runtime-work'/f'c230247-12b-{condition}-compat-v4'
        fixtures = []
        for kind in ('complete_motion','incomplete_motion','missing_evidence'):
            attempt = proof_root/condition/kind
            if attempt.exists():
                raise ValueError('Physical fixture scratch already exists')
            attempt.mkdir(parents=True)
            for name in ('config.json','trace.jsonl','video_frames.jsonl','result.json'):
                shutil.copyfile(source/name,attempt/name)
            if kind == 'incomplete_motion':
                rows = [json.loads(s) for s in (attempt/'trace.jsonl').read_text().splitlines()]
                first = rows[0]['position_m']
                for row in rows:
                    row['position_m'] = first
                    row['position'] = dict(zip(('x','y','z'),first))
                (attempt/'trace.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            if kind == 'missing_evidence':
                (attempt/'trace.jsonl').unlink()
            result_name = f'physical-{condition}-{kind}.json'
            log_name = f'physical-{condition}-{kind}.log'
            command = [sys.executable,str(FOLDER/'physical_outcome.py'),
                       '--attempt',str(attempt),'--case',entry['case_id'],
                       '--output',str(FOLDER/result_name)]
            env = dict(os.environ)
            env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO/'.runtime-work'/'c230247-12b-physical-import')
            env['TMPDIR'] = str(REPO/'.runtime-work')
            env['PYTHONDONTWRITEBYTECODE'] = '1'
            run = subprocess.run(command,env=env,text=True,capture_output=True)
            (FOLDER/log_name).write_text((run.stdout+run.stderr).rstrip()+'\n')
            if run.returncode:
                raise ValueError('Physical outcome proof failed: '+(run.stdout+run.stderr)[-500:])
            result = json.loads((FOLDER/result_name).read_text())
            fixtures.append({'kind':kind,'command':' '.join(command),
                             'exit_code':run.returncode,'log':log_name,
                             'log_sha256':sha(FOLDER/log_name),
                             'result':result_name,
                             'result_sha256':sha(FOLDER/result_name),
                             'observed':result['physical_checks']['maneuver']['status']})
        lifecycle_log = FOLDER/'physical-lifecycle.log'
        lifecycle_log.write_text('Synthetic CPU lifecycle ordering: capture_finished, encoders_closed, restoration_verified, native_exit, owner_released, saved_processing_started. Original Native owner release is not claimed.\n')
        proof = {'format':'c230247-red-x-physical-preparation-cpu-v1',
                 'case_id':entry['case_id'],
                 'construction_sha256':entry['construction_sha256'],
                 'fixtures':fixtures,
                 'lifecycle':{'events':['capture_finished','encoders_closed','restoration_verified','native_exit','owner_released','saved_processing_started'],
                              'exit_code':0,'log':lifecycle_log.name,
                              'log_sha256':sha(lifecycle_log)},
                 'original_native_observed':False,
                 'legal_verdict':None}
        path = FOLDER/f'physical-{condition}-preparation.json'
        path.write_text(json.dumps(proof,indent=2)+'\n')
        entry['physical_preparation']={'receipt':path.name,'sha256':sha(path)}
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'physical_outcomes':6,'manifest_sha256':sha(manifest_path)}))


if __name__ == '__main__':
    main()
