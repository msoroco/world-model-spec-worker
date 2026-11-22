"""Stage current-runtime selected candidates with their exact isolated CPU receipts.

This does not claim selected delivery or replace the canonical manifest.
"""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN_INTERSECTION = ROOT / '.runtime-work/c111662-directional-approach'
RUN_FALLBACK = ROOT / '.runtime-work/c111662-directional-fallbacks'
RUN_DIVIDED = ROOT / '.runtime-work/c111662-16'
PROOF = HERE / 'selected-current-proof'
OUT = HERE / 'selected-current-staging.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def retain(source, target):
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if target.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Oversized returned proof: ' + str(target))
    return str(target.relative_to(HERE))


def location(case, candidate):
    if case in ('reference', 'contrast'):
        if candidate == 'primary':
            variant = HERE / 'directional-approach-experiment'
            filename = ('directional-approach-experiment-manifest.json' if case == 'reference'
                        else 'directional-approach-contrast-experiment-manifest.json')
            attempt = RUN_INTERSECTION / ('compatibility' if case == 'reference'
                                          else 'contrast-compatibility')
            label = '' if case == 'reference' else 'contrast-'
        else:
            variant = HERE / 'directional-approach-experiment' / case / candidate
            filename = f'directional-approach-{case}-{candidate}-manifest.json'
            attempt = RUN_FALLBACK / case / candidate / 'compatibility'
            label = ''
    else:
        variant = HERE / 'current-16-experiment' / case / candidate
        filename = f'current-16-manifest-{case}-{candidate}.json'
        copies = [p for p in RUN_DIVIDED.glob(f'{case}-{candidate}-compatibility*')
                  if (p / 'compatibility.json').is_file() and
                  sha(p / 'compatibility.json') == sha(variant / 'compat-receipt.json')]
        if not copies:
            raise FileNotFoundError('No matching divided compatibility attempt: ' + case + '/' + candidate)
        attempt = sorted(copies)[-1]
        label = ''
    return variant, HERE / filename, attempt, label


def rebind(entry, case, candidate):
    variant, manifest_path, attempt, label = location(case, candidate)
    isolated = load(manifest_path)['cases'][0]
    source = isolated if candidate == 'primary' else next(
        c for c in isolated['candidates'] if c['id'] == candidate)
    selected = entry if candidate == 'primary' else next(
        c for c in entry['candidates'] if c['id'] == candidate)
    selected['construction'] = source['construction']
    selected['construction_sha256'] = source['construction_sha256']
    if sha(HERE / selected['construction']) != selected['construction_sha256']:
        raise ValueError('Construction changed: ' + case + '/' + candidate)
    if candidate == 'primary':
        entry['fixture_recipe'] = isolated['fixture_recipe']
    dest = PROOF / case / candidate
    offline = variant / f'pinned-{label}offline.log'
    retained = retain(offline, dest / 'offline.log')
    selected['offline'] = {
        'command': f'.venv-cpu/bin/python runtime.py offline --manifest {manifest_path.relative_to(ROOT)} '
                   f'--case {entry["case_id"]} --candidate {candidate}',
        'exit_code': 0,
        'construction_sha256': selected['construction_sha256'],
        'log': retained,
        'log_sha256': sha(HERE / retained),
    }
    receipt_path = attempt / 'compatibility.json'
    receipt = load(receipt_path)
    if not (receipt['passed'] is True and receipt['case_id'] == entry['case_id']
            and receipt['candidate_id'] == candidate
            and receipt['construction_sha256'] == selected['construction_sha256']):
        raise ValueError('Wrong compatibility receipt: ' + case + '/' + candidate)
    receipt_ref = retain(receipt_path, dest / 'compatibility.json')
    log_ref = retain(attempt / 'compatibility-analysis.log', dest / 'analysis.log')
    negative_ref = retain(attempt / 'negative-analysis.log', dest / 'negative-analysis.log')
    if sha(HERE / log_ref) != receipt['log_sha256'] or sha(HERE / negative_ref) != receipt['negative_log_sha256']:
        raise ValueError('Compatibility logs changed: ' + case + '/' + candidate)
    selected['compatibility'] = {
        'receipt': receipt_ref, 'sha256': sha(HERE / receipt_ref),
        'log': log_ref, 'negative_log': negative_ref,
    }
    if candidate == 'primary':
        entry['negative'] = {'log': negative_ref}
    return {'construction_sha256': selected['construction_sha256'],
            'offline_log_sha256': selected['offline']['log_sha256'],
            'compatibility_receipt_sha256': selected['compatibility']['sha256']}


def main():
    manifest = load(HERE / 'execution-manifest.json')
    manifest['runtime_manifest_sha256'] = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    manifest['status'] = 'staging_current_runtime_selected_cpu_proofs_partial'
    evidence = {}
    for entry in manifest['cases']:
        case = entry['case_id'].split('__')[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            evidence[f'{case}/{candidate}'] = rebind(entry, case, candidate)
        entry['preparation_status'] = 'partial: staged selected receipt binding; physical and delivery checks pending'
    save(OUT, manifest)
    save(PROOF / 'stage-evidence.json', {
        'format': 'c111662-current-selected-staging-v1',
        'status': 'staging_only_not_selected_delivery',
        'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
        'manifest_sha256': sha(OUT), 'candidates': evidence,
        'physical_receipts_rebound': False, 'strict_delivery_ready': False,
    })
    print(json.dumps({'manifest': str(OUT), 'candidate_receipts': len(evidence),
                      'sha256': sha(OUT)}))


if __name__ == '__main__':
    main()
