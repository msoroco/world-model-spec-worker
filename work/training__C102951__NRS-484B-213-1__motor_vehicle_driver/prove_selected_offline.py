"""Run current-runtime exact offline proofs for six selected construction drafts."""
import hashlib
import json
import os
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '/')).resolve()
    if not output_root.is_relative_to(ROOT / '.runtime-work'):
        raise ValueError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    from worker_exchange.runtime_cli import offline
    manifest = HERE / 'selected-draft-execution-manifest.json'
    source = json.loads(manifest.read_text())
    proof = []
    log_folder = HERE / 'selected-offline-proofs'
    log_folder.mkdir(exist_ok=True)
    for entry in source['cases']:
        for candidate in ('primary', 'fallback1'):
            case = entry['case_id']
            short = case.rsplit('__', 1)[-1]
            target = ROOT / '.runtime-work/c102951-selected-offline' / short / candidate
            if target.exists():
                shutil.rmtree(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            receipt = offline(manifest, case, target, str(ROOT / '.venv-cpu/bin/python'), candidate)
            log = log_folder / f'{short}-{candidate}.log'
            log.write_bytes(Path(receipt['log']).read_bytes())
            selected = (entry if candidate == 'primary' else entry['candidates'][0])
            proof.append({'case_id': case, 'candidate_id': candidate,
                          'construction_sha256': selected['construction_sha256'],
                          'offline_log': str(log.relative_to(HERE)),
                          'offline_log_sha256': sha(log),
                          'offline_passed': True, 'simulation_started': False})
    path = HERE / 'selected-offline-proof.json'
    path.write_text(json.dumps({'format': 'c102951-current-selected-draft-offline-v1',
                                'runtime_manifest_sha256': source['runtime_manifest_sha256'],
                                'cases': proof}, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'passed': len(proof), 'proof_sha256': sha(path)}))


if __name__ == '__main__':
    main()
