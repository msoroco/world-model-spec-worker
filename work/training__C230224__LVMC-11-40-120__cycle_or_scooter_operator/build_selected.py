"""Build exact path/roadway Native bundles and surveyed-spawn candidates."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
BASE = HERE/'native/selected_primary'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def main():
    original_runner = (BASE/'runner.py').read_text()
    original_test = (BASE/'tests/test_bundle.py').read_text()
    base_config = json.loads((BASE/'config.json').read_text())
    manifest = {'assignment_id': AID, 'cases': []}
    for suffix, primary_spawn, fallback_spawn in (
            ('probe_01', 'device_spawn_xyz_m', 'fallback_device_spawn_xyz_m'),
            ('probe_02', 'roadway_device_spawn_xyz_m', 'fallback_roadway_device_spawn_xyz_m')):
        case = AID+'__'+suffix
        entry = {'case_id': case, 'candidate_risk': {
            'status': 'physical',
            'reason': 'Reviewed rideable device/rider spawn and path or roadway placement may fail on the surveyed Native map'},
            'candidates': []}
        for candidate, spawn in (('primary', primary_spawn), ('fallback1', fallback_spawn)):
            config = dict(base_config)
            config.update(case_id=case, selected_case_id=case, candidate_id=candidate, spawn_key=spawn)
            runner = original_runner.replace("CASE = AID + '__probe_01'", "CASE = AID + '__"+suffix+"'")
            runner = runner.replace("cfg.get('candidate_id') != 'primary'", "cfg.get('candidate_id') != '"+candidate+"'")
            files = [{'path': 'runner.py', 'content': runner},
                     {'path': 'config.json', 'content': json.dumps(config, indent=2, sort_keys=True)+'\n'},
                     {'path': 'tests/test_bundle.py', 'content': original_test},
                     {'path': 'finalize_path.py', 'content': (HERE/'finalize_path.py').read_text()},
                     {'path': 'measure_path.py', 'content': (HERE/'native/measure_path.py').read_text()}]
            construction = {'format': 'worker-construction', 'assignment_id': AID,
                'case_id': case, 'cell_id': 'C230224', 'law_id': 'LVMC-11-40-120',
                'actor': 'cycle_or_scooter_operator', 'entrypoint': 'runner.py',
                'recording_description': config['recording_description'],
                'measurement_plan': {'entrypoint': 'finalize_path.py',
                    'source_files': ['video_frames.jsonl', 'native_rider_trace.jsonl', 'path_context.json'],
                    'legal_result': None}, 'files': files}
            path = HERE/('selected-primary-construction.json' if suffix == 'probe_01' and candidate == 'primary'
                else 'cases'/Path(suffix)/('fallback1-construction.json' if candidate == 'fallback1' else 'selected-primary-construction.json'))
            write(path, construction)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if candidate == 'primary':
                entry.update(construction=str(path.relative_to(HERE)), construction_sha256=digest)
                if suffix == 'probe_01':
                    (HERE/'runner.py').write_text(runner)
                    write(HERE/'config.json', config)
                    write(HERE/'construction.json', construction)
            else:
                entry['candidates'].append({'id': 'fallback1', 'construction': str(path.relative_to(HERE)),
                    'construction_sha256': digest, 'trigger': {'source': 'original Native spawn receipt',
                    'metric': 'device_spawn_failed', 'failure_condition': 'surveyed primary device spawn returns no actor'},
                    'changed_knobs': ['surveyed alternate device spawn transform']})
        manifest['cases'].append(entry)
    write(HERE/'selected-offline-manifest.json', manifest)
    print(json.dumps({'cases': [entry['case_id'] for entry in manifest['cases']]}, sort_keys=True))


if __name__ == '__main__':
    main()
