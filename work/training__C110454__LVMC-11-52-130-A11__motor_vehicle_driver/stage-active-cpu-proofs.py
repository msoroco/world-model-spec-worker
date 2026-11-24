"""Stage fresh active-runtime CPU chains and bind exact selected receipts."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')

def copy(source, target):
    if not source.is_file():
        raise ValueError('Fresh proof missing: ' + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    if target.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Returned proof exceeds 2 MiB: ' + str(target))
    return sha(target)

def main():
    runtime_hash = sha(ROOT / 'runtime/SOURCE-MANIFEST.json')
    selected_path = HERE / 'execution-manifest.json'
    selected = json.loads(selected_path.read_text())
    if selected['runtime_manifest_sha256'] != runtime_hash:
        raise ValueError('Selected manifest runtime binding differs')
    selected_by_id = {entry['case_id']: entry for entry in selected['cases']}
    summary = {'format': 'c110454-a11-active-runtime-cpu-proofs-v4', 'runtime_manifest_sha256': runtime_hash, 'synthetic_fixture': True, 'native_executed': False, 'physical_or_legal_acceptance_claimed': False, 'manifest_sha256': {}, 'public_chains': [], 'saved_primary_chains': []}
    for name in ('current-v2-witness-fallback-manifest.json', 'current-profile-statutory-manifest.json'):
        manifest_path = HERE / name
        manifest = json.loads(manifest_path.read_text())
        if manifest['runtime_manifest_sha256'] != runtime_hash:
            raise ValueError('Source manifest runtime binding differs: ' + name)
        summary['manifest_sha256'][name] = sha(manifest_path)
        for source_entry in manifest['cases']:
            case = source_entry['case_id']
            suffix = case.rsplit('__', 1)[-1]
            entry = selected_by_id[case]
            for candidate in [source_entry, *source_entry['candidates']]:
                cid = candidate['id']
                selected_candidate = entry if cid == 'primary' else next(x for x in entry['candidates'] if x['id'] == cid)
                compat = SCRATCH / 'c110454-active-compat' / suffix / cid
                offline = SCRATCH / 'c110454-active-offline' / suffix / cid
                stage = HERE / 'current-v4-active-proofs' / suffix / cid
                receipt = json.loads((compat / 'compatibility.json').read_text())
                if (receipt.get('passed') is not True or receipt.get('runtime_manifest_sha256') != runtime_hash or receipt.get('case_id') != case or receipt.get('candidate_id') != cid or receipt.get('construction_sha256') != candidate['construction_sha256'] or len(receipt.get('checks', [])) != 11):
                    raise ValueError('Fresh compatibility proof differs: ' + suffix + '/' + cid)
                if sha(ROOT / source_entry['fixture_recipe']) != receipt['fixture_recipe_sha256']:
                    raise ValueError('Fixture recipe changed: ' + suffix)
                rel = stage.relative_to(HERE)
                files = {}
                for filename in ('compatibility.json', 'compatibility-analysis.log', 'negative-analysis.log'):
                    target_name = 'public-analysis.log' if filename == 'compatibility-analysis.log' else filename
                    files[target_name] = copy(compat / filename, stage / target_name)
                files['offline.log'] = copy(offline / 'offline.log', stage / 'offline.log')
                if (files['public-analysis.log'] != receipt['log_sha256'] or files['negative-analysis.log'] != receipt['negative_log_sha256']):
                    raise ValueError('Fresh receipt log hash differs: ' + suffix + '/' + cid)
                selection = json.loads((offline / 'candidate-selection.json').read_text())
                if (selection['manifest_sha256'] != sha(manifest_path) or selection['construction_sha256'] != candidate['construction_sha256'] or selection['candidate_id'] != cid):
                    raise ValueError('Fresh offline selection differs: ' + suffix + '/' + cid)
                selected_candidate['offline'] = {'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + HERE.name + '/' + name + ' --case ' + case + ' --candidate ' + cid + ' --output .runtime-work/c110454-active-offline/' + suffix + '/' + cid, 'exit_code': 0, 'construction_sha256': candidate['construction_sha256'], 'log': (rel / 'offline.log').as_posix(), 'log_sha256': files['offline.log']}
                selected_candidate['compatibility'] = {'receipt': (rel / 'compatibility.json').as_posix(), 'sha256': files['compatibility.json'], 'log': (rel / 'public-analysis.log').as_posix(), 'negative_log': (rel / 'negative-analysis.log').as_posix()}
                if cid == 'primary':
                    entry['negative'] = {'log': (rel / 'negative-analysis.log').as_posix(), 'log_sha256': files['negative-analysis.log']}
                summary['public_chains'].append({'case_id': case, 'candidate_id': cid, 'construction_sha256': candidate['construction_sha256'], 'checks_passed': 11, 'files': {str(rel / key): value for key, value in files.items()}})
            saved = SCRATCH / 'c110454-active-saved' / suffix
            proof_path = saved / 'processed/v0001/processing.json'
            proof = json.loads(proof_path.read_text())
            if (proof.get('passed') is not True or proof.get('recorded_only') is not True or proof.get('originals_preserved') is not True or proof.get('case_id') != case or proof.get('candidate_id') != 'primary' or proof.get('analysis_revision', {}).get('runtime_manifest_sha256') != runtime_hash or proof.get('native_revision', {}).get('construction_sha256') != entry['construction_sha256'] or proof.get('timestamp_joins', {}).get('frames') != 600 or proof.get('final_video_checks', {}).get('passed') is not True):
                raise ValueError('Fresh saved primary proof differs: ' + suffix)
            saved_rel = Path('current-v4-active-saved') / suffix
            proof_sha = copy(proof_path, HERE / saved_rel / 'processing.json')
            log_sha = copy(saved / 'process-saved.log', HERE / saved_rel / 'process-saved.log')
            entry['saved_cpu_proof'] = {'processing': (saved_rel / 'processing.json').as_posix(), 'processing_sha256': proof_sha, 'recorded_only': True, 'originals_preserved': True, 'selected_construction_sha256': entry['construction_sha256']}
            summary['saved_primary_chains'].append({'case_id': case, 'construction_sha256': entry['construction_sha256'], 'processing': (saved_rel / 'processing.json').as_posix(), 'processing_sha256': proof_sha, 'process_saved_log_sha256': log_sha})
    if len(summary['public_chains']) != 33 or len(summary['saved_primary_chains']) != 11:
        raise ValueError('Active selected coverage incomplete')
    write(HERE / 'current-v4-active-cpu-proof.json', summary)
    write(selected_path, selected)
    print(json.dumps({'public_chains': 33, 'saved_primary_chains': 11, 'summary_sha256': sha(HERE / 'current-v4-active-cpu-proof.json'), 'selected_manifest_sha256': sha(selected_path)}))

if __name__ == '__main__':
    main()
