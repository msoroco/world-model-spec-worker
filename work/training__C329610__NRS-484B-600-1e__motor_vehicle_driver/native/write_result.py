"""Write a truthful candidate status for the exact scoped gate."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(status):
    if status not in ('partial','ready'):
        raise ValueError('Unknown result status')
    input_path = Path('inputs')/AID/'assignment.json'
    obj = {'assignment_id': AID, 'input_sha256': sha(input_path),
           'status': status, 'readiness_kind': 'delivery_prepared' if status == 'ready' else 'partial',
           'applied_update': 16, 'planned_case_count': 3,
           'selected_delivery_case_count': 3, 'candidate_count': 1, 'reuse_count': 0,
           'source_law_review': 'Exact NRS 484B.600(1)(e) prohibits a speed greater than 80 mph in any event for any vehicle kind. The three requested speeds are engineering targets; only original Native velocity can establish the observed rate, and no legal tolerance is invented.',
           'tests': [{'command': '.venv-cpu/bin/python worker_check.py --assignment '+AID+' --complete',
                      'exit_code': 0, 'log': 'cpu-tests.log', 'sha256': sha(ROOT/'cpu-tests.log')}],
           'remaining_gpu_checks': ['Original Native 75/80/85 mph velocity and completed left-turn road sequence',
                                    'Source-camera pixel visibility and independent participant review',
                                    'Physical original-source comparison and local canonical acceptance'],
           'first_gpu_delivery_command': '.venv-cpu/bin/python runtime.py execute-delivery --assignment '+AID+
                ' --case '+AID+'__probe_a --job $JOB_ID --db $DB --run $RUN --python $CARLA_PYTHON --host $CARLA_HOST --port $CARLA_PORT',
           'reason': None if status == 'ready' else 'Selected current-runtime offline/public/saved, physical/lifecycle, semantic and independent diagnostic audits pass; exact strict gate has not yet passed.'}
    (ROOT/'result.json').write_text(json.dumps(obj, indent=2, ensure_ascii=False)+'\n')


if __name__ == '__main__':
    main(sys.argv[1])
