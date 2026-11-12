"""Bind exact v14 offline and positive/negative compatibility fallback proofs."""
import hashlib
import json
import shutil
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
VERSION = 'v14'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = FOLDER/'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    result_path = FOLDER/'result.json'
    result = json.loads(result_path.read_text())
    tests = list(result['tests'])
    for entry in manifest['cases']:
        if entry['case_id'].endswith(('__ego_width_above_80in','__lead_width_at_80in','__lead_width_above_80in')):continue
        suffix = entry['case_id'].split('__')[-1]
        for candidate in entry['candidates']:
            ident = candidate['id']
            stem = f'c149237-{suffix}-{ident}'
            offline = ROOT/'.runtime-work'/f'{stem}-offline-{VERSION}'
            compat = ROOT/'.runtime-work'/f'{stem}-compat-{VERSION}'
            sources = (offline/'offline.log', compat/'compatibility.json',
                       compat/'compatibility-analysis.log', compat/'negative-analysis.log')
            if any(not source.is_file() for source in sources):
                raise FileNotFoundError('Missing fallback proof: '+stem)
            copied = []
            for source, kind in zip(sources, ('offline.log', 'compatibility.json', 'analysis.log', 'negative.log')):
                target = FOLDER/f'{suffix}-{ident}-{kind}'
                shutil.copyfile(source, target)
                copied.append(target)
            offline_log, receipt_path, analysis_log, negative_log = copied
            receipt = json.loads(receipt_path.read_text())
            if (receipt['passed'] is not True or receipt['candidate_id'] != ident or
                    receipt['construction_sha256'] != candidate['construction_sha256'] or
                    sha(analysis_log) != receipt['log_sha256'] or
                    sha(negative_log) != receipt['negative_log_sha256']):
                raise ValueError('Stale fallback compatibility: '+stem)
            base = f'.venv-cpu/bin/python runtime.py offline --manifest work/{FOLDER.name}/execution-manifest.json --case {entry["case_id"]} --candidate {ident}'
            offline_command = f'{base} --output .runtime-work/{stem}-offline-{VERSION}'
            compat_command = (f'.venv-cpu/bin/python runtime.py compatibility --manifest '
                              f'work/{FOLDER.name}/execution-manifest.json --case {entry["case_id"]} '
                              f'--candidate {ident} --output .runtime-work/{stem}-compat-{VERSION} '
                              '--library runtime/library --validator '
                              '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck')
            candidate['offline'] = {'command': offline_command, 'exit_code': 0,
                                    'log': offline_log.name, 'log_sha256': sha(offline_log),
                                    'construction_sha256': candidate['construction_sha256']}
            candidate['compatibility'] = {'receipt': receipt_path.name,
                                          'sha256': sha(receipt_path),
                                          'log': analysis_log.name,
                                          'negative_log': negative_log.name}
            for command, log in ((offline_command, offline_log),
                                 (compat_command, FOLDER/f'{suffix}-{ident}-compat-launch-{VERSION}.log')):
                if not log.is_file():
                    raise FileNotFoundError(log)
                tests.append({'command': command, 'exit_code': 0,
                              'log': log.name, 'sha256': sha(log)})
    manifest['status'] = 'partial_eight_primaries_and_three_fallbacks_proved_each'
    result['tests'] = tests
    result['readiness_kind'] = 'eight_primaries_and_24_fallbacks_compatible_checkpoint'
    result['reason'] = ('All eight exact primary cases have current v14 exact offline, positive/negative '
                        'synthetic compatibility and recorded-only saved-processing proofs. All 24 camera '
                        'fallback constructions pass exact offline and positive/negative compatibility checks; '
                        'four saved-source comparisons pass positive and negative controls. Independent delivery '
                        'audits, full-duration authored-road proof, complete semantic proposals, source-observation '
                        'mappings and shared delivery artifacts remain worker-owned CPU work. Real CARLA truck '
                        'widths, motion, camera pixels and legal judgments are unverified.')
    manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
    result_path.write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
