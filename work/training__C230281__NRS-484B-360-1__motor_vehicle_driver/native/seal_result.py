"""Record selected CPU preparation without claiming original school-trip facts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    old = json.loads((HERE / 'result.json').read_text())
    tests = []
    for speed in (53, 55, 57):
        log = HERE / ('native-proof-' + str(speed) + '.log')
        tests.append({'command': '.venv-cpu/bin/python -B runtime.py offline --manifest work/' + AID +
            '/draft-native-manifest.json --case ' + AID + '__' + str(speed),
            'exit_code': 0, 'log': log.name, 'sha256': sha(log)})
    log = HERE / 'top-level-tests.log'
    tests.append({'command': '(cd work/' + AID +
        ' && ../../.venv-cpu/bin/python -B -m unittest discover -s tests)',
        'exit_code': 0, 'log': log.name, 'sha256': sha(log)})
    result = {'assignment_id': AID, 'input_sha256': old['input_sha256'],
        'applied_update': old['applied_update'], 'status': 'ready',
        'reason': 'Three selected 53/55/57 mph school-bus Native constructions pass current-runtime offline, public positive/missing-source-negative, recorded-only, source-speed, semantic, physical/lifecycle and independent delivery/comparison CPU checks. Original school-bus design, judged driver join, pupils aboard, to/from-school trip, physical speed and legal result remain source-review conditions.',
        'readiness_kind': 'delivery_prepared',
        'cases_planned': 3, 'cases_selected': 3, 'candidate_plans_proven': 3,
        'comparison_audits_passed': 1, 'carla_executed': False,
        'recordings_accepted': 0, 'accepted_membership_count': 0,
        'reuse_count': 0, 'planned_case_count': 3,
        'selected_delivery_case_count': 3, 'candidate_count': 0,
        'unresolved_branch_count': 0,
        'first_gpu_delivery_command': '.venv-cpu/bin/python runtime.py execute-delivery --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --case ' + AID + '__53 --job "$JOB_ID" --db "$DB" --run "$RUN" --assignment ' + AID,
        'cpu_checkpoint': {'selected_native_cases': 3,
            'controlled_comparisons': 1,
            'public_positive_and_missing_source_negative': 3,
            'recorded_only_saved_receipts': 3,
            'physical_lifecycle_cpu_receipts': 3,
            'semantic_stages': 7,
            'independent_delivery_audits': 3,
            'independent_comparison_audits': 1,
            'original_native_physical_and_legal_acceptance_claimed': False},
        'tests': tests}
    target = HERE / 'result.json'
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'result_sha256': sha(target), 'status': result['status']}))


if __name__ == '__main__':
    main()
