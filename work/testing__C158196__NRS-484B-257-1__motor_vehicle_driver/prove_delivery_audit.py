"""Bind positive diagnostic and negative Native-provenance CPU audit proofs."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT/'execution-manifest.json'
ATTEMPTS = Path('.runtime-work/c158196-remaining-channels-sweep')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case_id = entry['case_id']
        suffix = case_id.rsplit('__',1)[-1]
        attempt = ATTEMPTS/(suffix+'-primary-compatibility')
        base = ['.venv-cpu/bin/python',str((ROOT/'delivery_audit.py').relative_to(REPO)),
                '--attempt',str(attempt),'--case',case_id]
        positive = base+['--diagnostic-fixture']
        negative = base
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        pos = subprocess.run(positive,cwd=REPO,env=env,capture_output=True,text=True)
        neg = subprocess.run(negative,cwd=REPO,env=env,capture_output=True,text=True)
        pos_log = ROOT/(suffix+'-delivery-positive.log')
        neg_log = ROOT/(suffix+'-delivery-negative.log')
        pos_log.write_text(pos.stdout+pos.stderr)
        neg_log.write_text(neg.stdout+neg.stderr)
        expected = 'Native source provenance required'
        if pos.returncode or neg.returncode == 0 or expected not in neg_log.read_text():
            raise ValueError('Independent delivery audit proof failed: '+suffix)
        output = json.loads(pos_log.read_text())
        if not output['software_audit_passed'] or output['physical_acceptance_claimed']:
            raise ValueError('Diagnostic delivery audit claimed physical acceptance')
        entry['delivery_acceptance'] = {
            'case_id':case_id,'sets':['demo-test'],
            'checks':['native_source','all_participants','time_join','full_video_decode',
                      'actual_pixels','physical_completion'],
            'script':'delivery_audit.py','script_sha256':sha(ROOT/'delivery_audit.py'),
            'command':shlex.join(positive),'test_exit_code':0,
            'test_log':pos_log.name,'test_log_sha256':sha(pos_log),
            'negative_command':shlex.join(negative),
            'negative_exit_code':neg.returncode,'negative_expected_error':expected,
            'negative_log':neg_log.name,'negative_log_sha256':sha(neg_log)}
        print(suffix,'positive 0 negative',neg.returncode,flush=True)
    MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')


if __name__ == '__main__':
    main()
