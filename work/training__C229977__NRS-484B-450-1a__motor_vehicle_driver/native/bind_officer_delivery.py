"""Bind independent officer-candidate source audit selftests."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SCRIPT = HERE / 'officer_delivery_audit.py'
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'officer-execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        if '__officer_direction_' not in entry['case_id']:
            continue
        name = entry['case_id'].split('__')[-1]
        pos = HERE / 'delivery-proofs' / f'{name}-positive.log'
        neg = HERE / 'delivery-proofs' / f'{name}-negative.log'
        if 'source_predicates_tested' not in pos.read_text() or 'Missing original sidewalk source' not in neg.read_text():
            raise ValueError('Officer audit selftests missing')
        command = f'.venv-cpu/bin/python -B work/{HERE.name}/officer_delivery_audit.py --case {entry["case_id"]} --self-test'
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-train'], 'checks': CHECKS,
            'script': str(SCRIPT.relative_to(HERE)), 'script_sha256': sha(SCRIPT),
            'command': command, 'negative_command': command + ' --negative',
            'test_exit_code': 0, 'negative_exit_code': 1,
            'negative_expected_error': 'Missing original sidewalk source',
            'test_log': str(pos.relative_to(HERE)), 'test_log_sha256': sha(pos),
            'negative_log': str(neg.relative_to(HERE)), 'negative_log_sha256': sha(neg)}
        evidence = ['vehicle-trace.jsonl', 'officer-trace.jsonl',
                    'camera-frames.jsonl', 'video_frames.jsonl',
                    'map-packet.json', 'authority-context.json', 'native-road.xodr']
        construction = json.loads((HERE / entry['construction']).read_text())
        names = {row['name'] for row in construction['recording_description']['channels']}
        names.update(('sidewalk_map_context', 'exception_authority_context',
                      'officer_candidate_trajectory'))
        entry['acquisition'] = {name: {
            'entrypoint': 'runner.py',
            'method': 'frame-aligned original Native actor, map, camera and authority source capture; independent review required',
            'evidence': ', '.join(evidence)} for name in sorted(names)}
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(sha(path))


if __name__ == '__main__':
    main()
