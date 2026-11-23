"""Reprove delivery-audit positive and negative paths after manifest binding."""
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
GROUPS = ('reference', 'contrast', 'conflict', 'clear', 'near_lead',
          'absent_lead', 'device_direction', 'officer_direction')
EXPECTED_ERROR = 'Original Native source required'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def command(group, output, diagnostic):
    case = HERE.name + '__' + group
    prefix = REPO / '.runtime-work' / ('c201084-final-' + group + '-primary')
    cmd = [str(REPO / '.venv-cpu/bin/python'), str(HERE / 'delivery_audit.py'),
           '--case', case, '--candidate', 'primary',
           '--attempt', str(prefix) + '-compatibility',
           '--processing', str(prefix) + '-saved/v0001/processing.json',
           '--output', str(output)]
    if diagnostic:
        cmd.append('--diagnostic')
    return cmd


def run(cmd, log):
    with log.open('w') as output:
        return subprocess.run(cmd, cwd=REPO, stdout=output,
                              stderr=subprocess.STDOUT, check=False).returncode


def main():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    require({case['case_id'] for case in manifest['cases']} ==
            {HERE.name + '__' + group for group in GROUPS},
            'Selected case coverage differs')
    for group in GROUPS:
        proof = HERE / 'delivery-proofs' / group
        proof.mkdir(parents=True, exist_ok=True)
        positive = proof / 'positive.json'
        negative = proof / 'rejected.json'
        require(not negative.exists(), 'Rejected audit output unexpectedly exists: ' + group)
        if positive.exists():
            previous = proof / 'previous-manifest-positive.json'
            require(not previous.exists(), 'Previous delivery audit already archived: ' + group)
            positive.rename(previous)
        pos_log = proof / 'positive.log'
        neg_log = proof / 'negative.log'
        for log in (pos_log, neg_log):
            if log.exists():
                previous = proof / ('previous-manifest-' + log.name)
                require(not previous.exists(), 'Previous audit log already archived: ' + group)
                log.rename(previous)
        require(run(command(group, positive, True), pos_log) == 0 and
                positive.is_file() and
                json.loads(positive.read_text())['accepted'] is False,
                'Diagnostic audit failed: ' + group)
        negative_code = run(command(group, negative, False), neg_log)
        require(negative_code != 0 and EXPECTED_ERROR in neg_log.read_text() and
                not negative.exists(),
                'Original Native rejection failed: ' + group)
        print(group, 'positive=0 negative=' + str(negative_code), flush=True)


if __name__ == '__main__':
    main()
