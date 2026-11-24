"""Exercise every canonical CLI selection and the missing-site rejection."""
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUNNER = ROOT / 'runner.py'


def run(args):
    return subprocess.run([sys.executable, str(RUNNER), *args],
                          text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=False)


def main():
    config = json.loads((ROOT / 'config.json').read_text())
    for case_id in config['supported_case_ids']:
        result = run(['--case', case_id, '--check'])
        if result.returncode != 0 or json.loads(result.stdout).get('case_id') != case_id:
            raise ValueError('Canonical selection failed: ' + case_id)
    invalid = run(['--case', config['assignment_id'] + '__absent', '--check'])
    if invalid.returncode == 0 or 'Unselected crossing case' not in invalid.stderr:
        raise ValueError('Unselected case was not rejected')
    no_site = run(['--case', config['supported_case_ids'][0], '--output-dir', '/tmp/not-used'])
    if no_site.returncode == 0 or 'Reviewed road intersection site' not in no_site.stderr:
        raise ValueError('Unsourced physical launch was not rejected')
    print(json.dumps({'selected_case_count': len(config['supported_case_ids']),
                      'invalid_case_rejected': True, 'unsourced_launch_rejected': True},
                     sort_keys=True))


if __name__ == '__main__':
    main()
