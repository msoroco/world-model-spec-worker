"""Bind source-hashed current v3 candidates to an explicit two-case execution plan."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def proof(probe, candidate):
    stem = f'{probe}-{candidate}'
    con = HERE / f'current-v3-{stem}-construction.json'
    log = HERE / 'current-v3-offline-proof' / f'{stem}.log'
    compat = HERE / 'current-v3-compat-proof' / stem
    saved = HERE / 'current-v3-saved-proof' / stem
    return {
        'construction': con.name,
        'construction_sha256': sha(con),
        'offline': {'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/current-v3-draft-manifest.json --case {HERE.name}__{probe} --candidate {candidate} --output .runtime-work/c10389-v3-current-offline/{stem}',
                    'exit_code': 0, 'construction_sha256': sha(con),
                    'log': str(log.relative_to(HERE)), 'log_sha256': sha(log)},
        'compatibility': {'receipt': str((compat / 'compatibility.json').relative_to(HERE)),
                          'sha256': sha(compat / 'compatibility.json'),
                          'log': str((compat / 'analysis.log').relative_to(HERE)),
                          'negative_log': str((compat / 'negative-analysis.log').relative_to(HERE))},
        'saved_cpu_proof': {'processing': str((saved / 'processing.json').relative_to(HERE)),
                            'processing_sha256': sha(saved / 'processing.json'),
                            'log': str((saved / 'analysis.log').relative_to(HERE)),
                            'log_sha256': sha(saved / 'analysis.log'),
                            'recorded_only': True, 'originals_preserved': True,
                            'selected_construction_sha256': sha(con)}}


draft = json.loads((HERE / 'current-v3-draft-manifest.json').read_text())
cases = []
for e in draft['cases']:
    probe = e['case_id'].rsplit('__', 1)[1]
    item = {k: v for k, v in e.items() if k not in ('kind', 'construction', 'construction_sha256', 'candidates')}
    item.update(proof(probe, 'primary'))
    item['kind'] = 'delivery'
    item['id'] = 'primary'
    item['candidates'] = []
    for c in e['candidates']:
        p = proof(probe, c['id'])
        p.update({k: v for k, v in c.items() if k not in ('construction', 'construction_sha256')})
        item['candidates'].append(p)
    phys = HERE / 'physical-proof' / probe / 'proof.json'
    item['physical_preparation'] = {'receipt': str(phys.relative_to(HERE)), 'sha256': sha(phys)}
    compat = HERE / 'current-v3-compat-proof' / f'{probe}-primary'
    item['negative'] = {'log': str((compat / 'negative-analysis.log').relative_to(HERE)),
                        'log_sha256': sha(compat / 'negative-analysis.log')}
    item['acquisition'] = {
        'kin.speed': {'entrypoint': 'capture.py',
                      'method': 'Retain original Native ego speed and frame identity at 20 Hz',
                      'evidence': 'native-raw-actors.jsonl joined to video_frames.jsonl'},
        'device_body': {'entrypoint': 'capture.py',
                        'method': 'Retain original Native ego body, device station and map readback',
                        'evidence': 'native-raw-actors.jsonl and native-map-readback.json; official placement remains unverified'}}
    item['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                              'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
    cases.append(item)
manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
            'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
            'cases': cases}
(HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(sha(HERE / 'execution-manifest.json'))
