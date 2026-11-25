"""Pin the eight selected cases and existing CPU offline receipts, status partial."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    draft = json.loads((HERE / 'execution-manifest.draft.json').read_text(encoding='utf-8'))
    plan = json.loads((HERE / 'case-plan.json').read_text(encoding='utf-8'))
    risks = {case['case_id']: case['physical_risk'] for case in plan['cases']}
    cases = []
    for row in draft['cases']:
        case_id = row['case_id']
        suffix = case_id.removeprefix(HERE.name + '__')
        log = 'cpu-semantic-offline-' + suffix + '.log'
        source = HERE / log
        if not source.is_file() or '"offline_passed": true' not in source.read_text(encoding='utf-8'):
            raise ValueError('selected case lacks passing offline proof: ' + case_id)
        construction = HERE / row['construction']
        if sha(construction) != row['construction_sha256']:
            raise ValueError('selected construction changed: ' + case_id)
        compatibility_receipt = HERE / ('receipt-compat-' + suffix + '.json')
        compatibility_log = HERE / ('analysis-compat-' + suffix + '.log')
        negative_log = HERE / ('negative-' + suffix + '.log')
        if compatibility_receipt.is_file() and compatibility_log.is_file():
            proof = json.loads(compatibility_receipt.read_text(encoding='utf-8'))
            if (proof.get('passed') is not True or proof.get('case_id') != case_id or
                    proof.get('construction_sha256') != row['construction_sha256'] or
                    proof.get('log_sha256') != sha(compatibility_log) or
                    proof.get('fixture_recipe_sha256') != sha(
                        HERE / ('fixture-recipe-' + suffix + '.json'))):
                raise ValueError('selected compatibility receipt is stale: ' + case_id)
            if not negative_log.is_file() or proof.get('negative_log_sha256') != sha(negative_log):
                raise ValueError('selected negative compatibility proof is stale: ' + case_id)
            compatibility = {'receipt': compatibility_receipt.name,
                             'sha256': sha(compatibility_receipt),
                             'log': compatibility_log.name}
        else:
            compatibility = {'status': 'pending_cpu_positive_and_negative'}
        delivery_script = HERE / 'delivery_audit.py'
        delivery_positive = HERE / ('cpu-delivery-' + suffix + '.log')
        delivery_negative = HERE / ('cpu-delivery-negative-' + suffix + '.log')
        if all(path.is_file() for path in (delivery_script, delivery_positive, delivery_negative)):
            acceptance = {
                'case_id': case_id, 'sets': ['full-test'],
                'checks': ['native_source', 'all_participants', 'time_join',
                           'full_video_decode', 'actual_pixels', 'physical_completion'],
                'script': delivery_script.name, 'script_sha256': sha(delivery_script),
                'command': '.venv-cpu/bin/python work/' + HERE.name +
                           '/delivery_audit.py --case ' + case_id + ' --self-test',
                'test_exit_code': 0, 'test_log': delivery_positive.name,
                'test_log_sha256': sha(delivery_positive),
                'negative_command': '.venv-cpu/bin/python work/' + HERE.name +
                                    '/delivery_audit.py --case ' + case_id +
                                    ' --self-test --tamper',
                'negative_exit_code': 1,
                'negative_expected_error': 'actual four-camera participant visibility unconfirmed',
                'negative_log': delivery_negative.name,
                'negative_log_sha256': sha(delivery_negative),
            }
            if acceptance['negative_expected_error'] not in delivery_negative.read_text():
                raise ValueError('selected delivery negative proof is stale: ' + case_id)
        else:
            acceptance = {'status': 'pending_independent_saved_proof'}
        saved_log = HERE / ('cpu-process-saved-' + suffix + '.log')
        physical_receipt = HERE / ('physical-preparation-' + suffix + '.json')
        if not physical_receipt.is_file():
            raise ValueError('missing CPU physical preparation proof: ' + case_id)
        fallback_name = 'construction-fallback1-' + suffix + '.json'
        fallback = HERE / fallback_name
        if not fallback.is_file():
            raise ValueError('missing constructed physical fallback: ' + case_id)
        fallback_sha = sha(fallback)
        fallback_offline_log = HERE / ('cpu-fallback-offline-' + suffix + '.log')
        fallback_receipt = HERE / ('receipt-fallback1-compat-' + suffix + '.json')
        fallback_compat_log = HERE / ('analysis-fallback1-compat-' + suffix + '.log')
        fallback_negative_log = HERE / ('negative-fallback1-' + suffix + '.log')
        fallback_entry = {
            'id': 'fallback1', 'construction': fallback_name,
            'construction_sha256': fallback_sha,
            'trigger': {
                'source': 'original Native 900-frame ego control history and sourced encounter zone',
                'metric': 'ego route progress at frame 899 versus encounter zone entry',
                'failure_condition': 'ego has not entered the sourced encounter zone by frame 899',
            },
            'changed_knobs': ['CARLA ego throttle speed-tracking gain 0.25 to 0.35; target speeds, route, cameras, 20 Hz and 900 frames held fixed'],
        }
        if fallback_offline_log.is_file():
            if '"offline_passed": true' not in fallback_offline_log.read_text(encoding='utf-8'):
                raise ValueError('fallback offline proof is not passing: ' + case_id)
            fallback_entry['offline'] = {
                'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + HERE.name +
                           '/execution-manifest.json --case ' + case_id + ' --candidate fallback1' +
                           ' --output .runtime-work/c111304-fallback-offline-' + suffix +
                           ' --python ' + str(REPO / '.venv-cpu/bin/python'),
                'construction_sha256': fallback_sha, 'exit_code': 0,
                'log': fallback_offline_log.name, 'log_sha256': sha(fallback_offline_log),
            }
        if all(path.is_file() for path in (fallback_receipt, fallback_compat_log, fallback_negative_log)):
            receipt = json.loads(fallback_receipt.read_text(encoding='utf-8'))
            if (receipt.get('passed') is not True or receipt.get('case_id') != case_id or
                    receipt.get('candidate_id') != 'fallback1' or
                    receipt.get('construction_sha256') != fallback_sha or
                    receipt.get('log_sha256') != sha(fallback_compat_log) or
                    receipt.get('negative_log_sha256') != sha(fallback_negative_log)):
                raise ValueError('fallback compatibility receipt is stale: ' + case_id)
            fallback_entry['compatibility'] = {
                'receipt': fallback_receipt.name, 'sha256': sha(fallback_receipt),
                'log': fallback_compat_log.name,
                'negative_log': fallback_negative_log.name,
            }
        post_capture = {
            'recorded_only': True,
            'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' +
                       HERE.name + '/execution-manifest.json --case ' + case_id +
                       ' --attempt "$ATTEMPT" --output "$OUTPUT" --library runtime/library'
                       ' --validator "$VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"',
            'feedback_command': 'cat "$OUTPUT"/v0001/feedback.json # ' + case_id,
        }
        if saved_log.is_file():
            post_capture.update(test_exit_code=0, test_log=saved_log.name,
                                test_log_sha256=sha(saved_log))
        cases.append({
            'case_id': case_id, 'kind': 'delivery', 'preparation_status': 'partial',
            'construction': row['construction'],
            'construction_sha256': row['construction_sha256'],
            'candidate_risk': risks[case_id], 'candidates': [fallback_entry],
            'physical_preparation': {'receipt': physical_receipt.name,
                                     'sha256': sha(physical_receipt)},
            'offline': {
                'command': '.venv-cpu/bin/python runtime.py offline --manifest '
                           'work/' + HERE.name + '/execution-manifest.draft.json --case '
                           + case_id + ' --output .runtime-work/c111304-offline-'
                           + suffix + '-semantic-v7 --python ' + str(REPO / '.venv-cpu/bin/python'),
                'construction_sha256': row['construction_sha256'],
                'exit_code': 0, 'log': log, 'log_sha256': sha(source),
            },
            'measurement_contract': 'measurement-contract.json',
            **({'fixture_recipe': 'work/' + HERE.name + '/fixture-recipe-' + suffix + '.json'}
               if (HERE / ('fixture-recipe-' + suffix + '.json')).is_file() else {}),
            'measurement_procedure': {'entrypoint': 'analysis.py'},
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT',
                               'site_env_var': 'C111304_SITE_SOURCE',
                               'access_env_var': 'C111304_ACCESS_SOURCE',
                               'access_review_env_var': 'C111304_ACCESS_REVIEW',
                               'camera_plan_env_var': 'C111304_CAMERA_PLAN'},
            'acquisition': {
                name: {'entrypoint': 'analysis.py', 'method': 'analyze',
                       'evidence': 'sealed Native actor, control and camera packet sources'}
                for name in ('access_context', 'driver_control_history',
                             'person_encounter', 'property_encounter',
                             'original_camera_frame_join')
            },
            'compatibility': compatibility,
            **({'negative': {'log': negative_log.name}}
               if compatibility_receipt.is_file() else {}),
            'delivery_acceptance': acceptance,
            'post_capture': post_capture,
        })
    manifest = {
        'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
        'preparation_status': 'partial',
        'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
        'cases': cases,
    }
    (HERE / 'execution-manifest.json').write_text(
        json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    proven = sum('receipt' in case['compatibility'] for case in cases)
    print('pinned', len(cases), 'selected C111304 cases;', proven,
          'diagnostic compatibility receipts verified')


if __name__ == '__main__':
    main()
