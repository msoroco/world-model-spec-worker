"""Execute exact fallback1 offline and public diagnostic proofs, one case at a time."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'preview-fallback-compatibility-manifest.json'
WORK = REPO / '.runtime-work/c146314-210-1'
VALIDATOR = REPO / '.runtime-work/c102372-active-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return str(path.relative_to(ROOT))


def main():
    assert '.runtime-work' in Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve().parts
    assert Path(os.environ['TMPDIR']).resolve() == WORK.resolve()
    manifest = json.loads(MANIFEST.read_text())
    draft_path = ROOT / 'draft-selected-execution-manifest.json'
    draft = json.loads(draft_path.read_text())
    by_case = {entry['case_id']: entry for entry in draft['cases']}
    for source_entry in manifest['cases']:
        case = source_entry['case_id']
        suffix = case.split('__')[-1]
        candidate = source_entry['candidates'][0]
        target = ROOT / candidate['construction']
        bundle = target.parent
        offline_output = WORK / ('fallback-v4-offline-' + suffix)
        offline_cmd = [sys.executable, str(REPO / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', case,
                       '--candidate', 'fallback1', '--output', str(offline_output)]
        subprocess.run(offline_cmd, cwd=REPO, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.STDOUT)
        offline_source = offline_output / 'offline.log'
        offline_log = bundle / 'offline.log'
        shutil.copyfile(offline_source, offline_log)
        candidate['offline'] = {'command': ' '.join(offline_cmd),
                                'construction_sha256': sha(target),
                                'exit_code': 0, 'log': relative(offline_log),
                                'log_sha256': sha(offline_log)}
        public_output = WORK / ('fallback-v4-public-' + suffix)
        public_cmd = [sys.executable, str(REPO / 'runtime.py'), 'compatibility',
                      '--manifest', str(MANIFEST), '--case', case,
                      '--candidate', 'fallback1', '--output', str(public_output),
                      '--library', str(REPO / 'runtime/library'),
                      '--validator', str(VALIDATOR)]
        subprocess.run(public_cmd, cwd=REPO, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.STDOUT)
        receipt = bundle / 'compatibility.json'
        analysis_log = bundle / 'public-analysis.log'
        negative_log = bundle / 'negative-analysis.log'
        shutil.copyfile(public_output / 'compatibility.json', receipt)
        shutil.copyfile(public_output / 'compatibility-analysis.log', analysis_log)
        shutil.copyfile(public_output / 'negative-analysis.log', negative_log)
        source_receipt = json.loads(receipt.read_text())
        assert source_receipt['candidate_id'] == 'fallback1'
        assert source_receipt['construction_sha256'] == sha(target)
        assert source_receipt['log_sha256'] == sha(analysis_log)
        assert source_receipt['negative_log_sha256'] == sha(negative_log)
        candidate['compatibility'] = {'receipt': relative(receipt),
                                      'sha256': sha(receipt),
                                      'log': relative(analysis_log),
                                      'negative_log': relative(negative_log)}
        selected = by_case[case]
        selected['candidate_risk'] = source_entry['candidate_risk']
        selected['candidates'] = [candidate]
        selected['remaining_cpu_bindings'] = [item for item in selected['remaining_cpu_bindings']
                                               if item != 'risk_fallbacks']
        draft_path.write_text(json.dumps(draft, indent=2, allow_nan=False) + '\n')
        print('PASS fallback1 exact offline/public positive-negative:', suffix, flush=True)
    print('PASS all 13 fallback1 constructions and public diagnostic receipts', flush=True)


if __name__ == '__main__':
    main()
