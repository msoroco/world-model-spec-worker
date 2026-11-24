"""Bind current public/saved/physical proofs to the four exact delivery cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    proof = json.loads((HERE / 'current-public/proof.json').read_text())
    if proof['selected_manifest_sha256'] != sha(manifest_path) or len(proof['chains']) != 12:
        raise ValueError('Current twelve-chain proof differs from selected draft')
    chains = {(row['case_id'], row['candidate']): row for row in proof['chains']}
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    ids = [case['case_id'] for case in plan['cases']]
    for case in plan['cases']:
        case['kind'] = 'delivery_prepared_cpu'
    plan['selected_branch'] = plan['witness_branches'][0]
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'whole alley crossing and pedestrian signal', 'interval': 'all 600 frames'},
            {'view': 'approach', 'subject': 'pedestrian approach and first highway entry', 'interval': 'all 600 frames'},
            {'view': 'reference_corner', 'subject': 'pedestrian body and authored crossing edges', 'interval': 'all 600 frames'},
            {'view': 'driver_reference', 'subject': 'signal icon, illumination and direction', 'interval': 'all 600 frames'},
        ],
    }
    terms = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())['source_observation_terms']
    mapping = {}
    for item in terms:
        term = item['term']
        channels = (['native_display_program', 'display_camera_frame_join'] if term.startswith('dev.') else
                    ['kin.position', 'rel.occupies'] if term in ('ru.subject', 'drv.entering_intersection') else
                    ['kin.position'] if term == 'kin.speed' else ['rel.occupies'])
        mapping[term] = {'evidence': item['note'] + '; original physical source review pending',
                         'channels': channels,
                         'source_refs': ['steady-samples.jsonl', 'exception-samples.jsonl',
                                         'video_frames.jsonl', 'driver_reference.mkv']}
    plan['source_observation_mapping'] = mapping
    write(plan_path, plan)
    for entry in manifest['cases']:
        suffix = entry['case_id'][len(HERE.name) + 2:]
        group = 'draft-bundles' if suffix.startswith('witness') else 'draft-exception-bundles'
        physical = HERE / 'physical-proof' / suffix / 'proof.json'
        entry['physical_preparation'] = {'case_id': entry['case_id'],
                                         'receipt': physical.relative_to(HERE).as_posix(),
                                         'sha256': sha(physical)}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        construction = json.loads((HERE / entry['construction']).read_text())
        config = json.loads(next(item['content'] for item in construction['files'] if item['path'] == 'config.json'))
        names = set(config['required_atoms']) | {row['name'] for row in construction['recording_description']['channels']}
        source = ('steady' if suffix.startswith('witness') else 'exception') + '-samples.jsonl'
        entry['acquisition'] = {name: {'entrypoint': 'finalize.py',
                                        'evidence': source + ', video_frames.jsonl, capture/evidence.jsonl',
                                        'method': 'rebuild from original timestamp joined Native rows and camera frames'}
                                for name in sorted(names)}
        for candidate in ('primary', 'fallback1', 'fallback2'):
            selected = entry if candidate == 'primary' else next(row for row in entry['candidates'] if row['id'] == candidate)
            row = chains[(entry['case_id'], candidate)]
            artifacts = row['artifacts']
            offline_path = HERE / group / suffix / candidate / 'draft-receipt.json'
            offline = json.loads(offline_path.read_text())
            if offline['construction_sha256'] != selected['construction_sha256'] or offline['exit_code'] != 0:
                raise ValueError('Exact offline proof differs: ' + suffix + '/' + candidate)
            selected['offline'] = {'command': offline['command'], 'exit_code': 0,
                                   'construction_sha256': selected['construction_sha256'],
                                   'log': offline['command_log'], 'log_sha256': offline['command_log_sha256']}
            selected['compatibility'] = {'receipt': artifacts['compatibility']['path'],
                                         'sha256': artifacts['compatibility']['sha256'],
                                         'log': artifacts['analysis_log']['path'],
                                         'negative_log': artifacts['negative_log']['path']}
            selected['negative'] = {'log': artifacts['negative_log']['path']}
            selected['saved_processing'] = {'receipt': artifacts['processing']['path'],
                                            'sha256': artifacts['processing']['sha256']}
            if candidate == 'primary':
                entry['post_capture'] = {
                    'recorded_only': True,
                    'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' + HERE.name +
                               '/execution-manifest.json --case ' + entry['case_id'] +
                               ' --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT" --library runtime/library --validator "$DECODER"',
                    'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
                    'test_exit_code': 0,
                    'test_log': artifacts['processing']['path'],
                    'test_log_sha256': artifacts['processing']['sha256'],
                }
    write(manifest_path, manifest)
    root = json.loads((HERE / manifest['cases'][0]['construction']).read_text())
    config = json.loads(next(item['content'] for item in root['files'] if item['path'] == 'config.json'))
    config['supported_case_ids'] = ids
    for camera in config['cameras']:
        camera['pose_strategy'] = 'authored crossing overview' if camera['name'] == 'overview' else 'original pedestrian and signal view'
        camera['fov_deg'] = 90
    for item in root['files']:
        if item['path'] == 'config.json':
            item['content'] = json.dumps(config, indent=2) + '\n'
        destination = HERE / item['path']
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(item['content'])
    write(HERE / 'construction.json', root)
    print(json.dumps({'selected_cases': len(manifest['cases']), 'candidate_chains': len(chains),
                      'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
